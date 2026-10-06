"""Pure Markdown presentation of existing Dashboard fields; no evidence verdicts."""
from datetime import datetime, timedelta, timezone
import json
import re


STATE_LABELS = {
    "IMPLEMENTING": "実装中",
    "REVIEWING": "レビュー・検証の確認待ち",
    "FIX_REQUIRED": "修正または阻害条件の解消が必要（修正開始は別確認）",
    "READY_FOR_HUMAN_MERGE": "条件成立・人間のマージ判断待ち",
    "MERGED_SYNC_PENDING": "マージ済み・正式同期の確認待ち",
    "LOCAL_SYNCED": "正式同期済み・完了条件の確認待ち",
    "COMPLETED": "必須完了条件が成立",
    "SAFE_STOPPED": "安全停止・根拠の確認または判断が必要",
}
STATUS_LABELS = {
    "PASS": "条件成立", "PENDING": "確認待ち", "BLOCKED": "阻害条件あり",
    "STALE": "対象または証拠が古い", "ERROR": "根拠・状態を検証できない",
    "NOT_REQUIRED": "今回の承認済み範囲では不要",
}
DISPATCH_LABELS = {
    "REQUESTED": "依頼記録あり・実受領と開始は別確認",
    "DISPATCHING": "起動操作中・外部実状態の確認待ち",
    "RUNNING": "実行中として記録", "SUCCEEDED": "成功として記録",
    "FAILED": "失敗として記録", "CANCELLED": "取消として記録",
    "UNKNOWN": "外部実状態が不明",
}
CONDITION_LABELS = {
    "live_smoke": "live smoke", "windows_validation": "Windows実機validation",
    "windows_measurement": "Windows実機測定", "artifact_integrity": "artifact整合性",
    "measurement_result_pr": "測定結果PR",
}


def plain(value):
    """Escape untrusted prose, including Markdown/autolinks and marker lookalikes."""
    if value is None or value == "":
        return "未取得"
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    value = str(value).replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    return "".join(f"&#{ord(c)};" if c in "&<>|\\`*_[]~!#@:/." else c for c in value)


def described(value, labels):
    if value is None or value == "":
        return "未取得"
    label = labels.get(value, "説明未定義") if isinstance(value, str) else "説明未定義"
    return plain(value) + " — " + label


def positive_id(value):
    # Sync evidence stores some IDs as strings. Never accept bool, zero or paths.
    return ((type(value) is int and value > 0)
            or (isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value) is not None))


def reference(state, repository, kind, value):
    valid = positive_id(value)
    if kind == "commit":
        valid = isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None
    if state.get("repository") != repository or not valid:
        return plain(value)
    root = f"https://github.com/{repository}"
    paths = {"issue": "issues", "pr": "pull", "commit": "commit", "run": "actions/runs"}
    if kind == "comment":
        if not positive_id(state.get("pr")):
            return plain(value)
        url = f'{root}/pull/{state["pr"]}#issuecomment-{value}'
    else:
        url = f"{root}/{paths[kind]}/{value}"
    return f"[{plain(value)}]({url})"


def updated_time(value):
    original = plain(value)
    if value is None or value == "":
        return original
    try:
        # Require a complete timezone-bearing ISO timestamp. No local-time guesses.
        if not isinstance(value, str) or re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value) is None:
            raise ValueError("Not an aware timestamp")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        jst = parsed.astimezone(timezone(timedelta(hours=9))).isoformat()
    except (ValueError, TypeError, OverflowError):
        return original + " / JST: 解析不能"
    return original + "（元値） / JST: " + plain(jst)


def table(rows):
    return "| 項目 | 現在値 |\n|---|---|\n" + "\n".join(
        f"| {plain(name)} | {value} |" for name, value in rows)


def head_comparison(target, current):
    if target is None or current is None:
        return "照合未確認"
    if not (isinstance(target, str) and isinstance(current, str)
            and re.fullmatch(r"[0-9a-f]{40}", target) and re.fullmatch(r"[0-9a-f]{40}", current)):
        return "照合未確認"
    return "現在PR headと一致" if target == current else "現在PR headと不一致"


def evidence(state, repository, item, compare_head=False, identities=()):
    if not isinstance(item, dict):
        return plain(item)
    parts = [described(item.get("status"), STATUS_LABELS), "理由: " + plain(item.get("reason"))]
    fields = [("head_sha", "対象head SHA", "commit"), ("target_sha", "対象target SHA", "commit"),
              ("run_id", "Actions run ID", "run"), ("run_attempt", "run attempt", None),
              ("comment_id", "Work結果comment ID", "comment")]
    for key, label, kind in fields:
        if key not in identities and key not in item:
            continue
        # Show missing diagnostic identities explicitly, never borrow current head.
        value = item.get(key)
        parts.append(label + ": " + (reference(state, repository, kind, value) if kind else plain(value)))
        if key == "head_sha" and compare_head:
            parts.append(head_comparison(value, state.get("head_sha")))
    return " / ".join(parts)


def records(state, repository, items):
    if not isinstance(items, list):
        return plain(items)
    if not items:
        return "なし（stateの明示的な空配列）"
    parts = []
    kinds = {"issue": "issue", "pr": "pr", "head_sha": "commit", "merge_sha": "commit",
             "run_id": "run", "comment_id": "comment"}
    for item in items:
        if isinstance(item, dict):
            parts.append("; ".join(plain(key) + ": " + (
                reference(state, repository, kinds[key], value) if key in kinds else plain(value))
                for key, value in sorted(item.items())))
        else:
            parts.append(plain(item))
    return "<br>".join(parts)


def render_markdown(state, repository):
    """Read-only projection. All machine data remains in the existing JSON block."""
    ref = lambda kind, value: reference(state, repository, kind, value)
    identities = {
        "work_review": ("head_sha", "comment_id"),
        "ci_ubuntu": ("head_sha", "run_id", "run_attempt"),
        "ci_windows": ("head_sha", "run_id", "run_attempt"),
        "public_data": ("head_sha", "run_id", "run_attempt"),
        "local_sync": ("target_sha", "run_id", "run_attempt"),
    }
    ev = lambda key, compare=False: evidence(
        state, repository, state.get(key), compare, identities.get(key, ()))
    merge_gate = ev("merge_gate")
    if state.get("merge_state") == "MERGED" and (state.get("merge_gate") or {}).get("status") == "BLOCKED":
        merge_gate += " / マージ済みのため、新たなマージ許可の対象外"
        if state.get("current_state") == "COMPLETED":
            merge_gate += "。COMPLETEDは完了条件の成立、Merge Gateは新たなマージ許可を表すため併存します"
    sections = ["## LangBench-Live Automation Dashboard", "### 状態・Gate・blocker",
                table([("現在状態", described(state.get("current_state"), STATE_LABELS)),
                       ("Merge Gate", merge_gate), ("Completion Gate", ev("completion_gate")),
                       ("現在のblocker", records(state, repository, state.get("blockers")))]),
                "### Issue・PR・SHA",
                table([("Issue", ref("issue", state.get("issue"))), ("開発目的", plain(state.get("purpose"))),
                       ("PR", ref("pr", state.get("pr"))), ("現在PR head SHA", ref("commit", state.get("head_sha"))),
                       ("マージ状態", described(state.get("merge_state"), {"MERGED": "マージ済み", "PENDING": "確認待ち"})),
                       ("merge SHA", ref("commit", state.get("merge_sha")))]),
                "### Workレビュー・CI・公開データ",
                table([("Workレビュー", ev("work_review", True)), ("Ubuntu CI", ev("ci_ubuntu", True)),
                       ("Windows CI", ev("ci_windows", True)), ("必須CI全体", ev("required_ci")),
                       ("CI認定head SHA", ref("commit", state.get("ci_head_sha"))),
                       ("公開データ検算", ev("public_data", True))]),
                "### 正式同期・live smoke・必要条件"]
    rows = [("正式同期", ev("local_sync")),
            ("同期target SHA", ref("commit", state.get("local_sync_target_sha")))]
    requirements, conditions = state.get("requirements") or {}, state.get("conditions") or {}
    names = ["live_smoke", "windows_validation", "windows_measurement", "artifact_integrity", "measurement_result_pr"]
    names += sorted((set(requirements) | set(conditions)) - set(names))
    for name in names:
        requirement = described(requirements.get(name), {
            "REQUIRED": "今回の必須条件", "NOT_REQUIRED": STATUS_LABELS["NOT_REQUIRED"]})
        rows.append((CONDITION_LABELS.get(name, name), requirement + " / " + evidence(
            state, repository, conditions.get(name))))
    sections += [table(rows), "### 担当・dispatch",
                 table([("現在担当", plain(state.get("current_actor"))),
                        ("Dispatch owner（active action）", plain((state.get("dispatch_owners") or {}).get(state.get("active_action")))),
                        ("action", plain(state.get("active_action"))), ("purpose", plain(state.get("purpose_id"))),
                        ("dispatch状態", described(state.get("dispatch_state"), DISPATCH_LABELS)),
                        ("run / task ID（URLは推測しない）", plain(state.get("active_run_id"))),
                        ("共通dedup key", plain(state.get("dedup_key")))]),
                 "### 診断詳細・履歴・更新時刻",
                 table([("FOLLOW_UP", records(state, repository, state.get("follow_up"))),
                        ("FOLLOW_UP記録", plain(state.get("follow_up_recorded"))),
                        ("最終遷移", plain(state.get("last_transition"))),
                        ("Dashboard最終更新", updated_time(state.get("last_updated")))]),
                 "<details>\n<summary>証拠の全フィールド・owner・dispatch履歴</summary>\n"]
    # Retain less common evidence fields and complete receipts in visible diagnostics.
    keys = ["work_review", "required_ci", "ci_ubuntu", "ci_windows", "public_data", "local_sync",
            "merge_gate", "completion_gate", "conditions", "requirements", "dispatch_owners"]
    history = []
    for item in state.get("dispatches") or []:
        if not isinstance(item, dict):
            history.append(("dispatch（説明未定義）", plain(item)))
            continue
        history.append(("dispatch", " / ".join([
            "action: " + plain(item.get("action_type")), "purpose: " + plain(item.get("purpose_id")),
            described(item.get("state"), DISPATCH_LABELS), "対象SHA: " + ref("commit", item.get("target_sha")),
            "run / task ID: " + plain(item.get("run_id")), "attempt: " + plain(item.get("attempt")),
            "retry_of: " + plain(item.get("retry_of")), "全フィールド: " + plain(item)])))
    sections += [table([(key, plain(state.get(key))) for key in keys]),
                 "dispatch履歴（全件）", table(history) if history else "なし（stateの明示的な空配列）", "</details>"]
    return "\n\n".join(sections)
