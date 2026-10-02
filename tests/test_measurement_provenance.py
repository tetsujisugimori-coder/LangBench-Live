import copy
import unittest

from tools.measurement_provenance import compare_conditions, validate_manifest_v2


def manifest():
    source = lambda p: {"path": p, "sha256": "a" * 64}
    return {"schema_version":"2.0","measurement_git_sha":"b"*40,"benchmark":"function_call_numeric_sum","experiment_id":"run","runner":{"path":"run.ps1","sha256":"c"*64},"os":"Windows","architecture":"x64","measurement_order":["direct","function_call"],"languages":{
        "c":{"source":source("main.c"),"runtime":{"name":"native","version":"native"},"compiler":{"name":"gcc","version":"16.1.0"},"options":["-O2"]},
        "python":{"source":source("main.py"),"runtime":{"name":"Python","version":"3.14.7"},"implementation":{"name":"CPython","version":"3.14.7"},"optimize":0,"options":["optimize=0"]},
        "javascript":{"source":source("main.js"),"runtime":{"name":"Node.js","version":"v24.20.0"},"implementation":{"name":"V8","version":"13.6"},"exec_argv":[],"node_options":"","options":[]}}}


class MeasurementProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.m = manifest()
        self.js = {"source_sha256":"a"*64,"architecture":"x64","options":[],"runtime":{"name":"Node.js","version":"v24.20.0"},"implementation":{"name":"V8","version":"13.6"}}

    def test_v2_validates_all_recorded_identities(self):
        self.assertEqual([], validate_manifest_v2(self.m))

    def test_required_type_version_and_hash_validation(self):
        mutations = [("missing", lambda x:x.pop("runner")),("version",lambda x:x.update(schema_version="1.0")),("hash",lambda x:x["languages"]["c"]["source"].update(sha256="bad")),("type",lambda x:x["languages"]["python"].update(optimize="0"))]
        for name, mutate in mutations:
            with self.subTest(name=name):
                value=copy.deepcopy(self.m); mutate(value); self.assertTrue(validate_manifest_v2(value))

    def test_thirteen_comparison_cases_fail_closed(self):
        # 1 full match
        self.assertTrue(compare_conditions(self.m,self.js,"javascript")["exact_applicability"])
        cases=[]
        for field in ("implementation", "runtime"):
            a=copy.deepcopy(self.js); a[field]["version"]="other"; cases.append(a) # 2,4
        a=copy.deepcopy(self.m); del a["languages"]["javascript"]["implementation"]; cases.append((a,self.js,"javascript")) # 3
        py={"source_sha256":"a"*64,"architecture":"x64","options":["optimize=0"],"implementation":{"name":"CPython","version":"3.14.7"},"optimize":0}
        for value in (1,None):
            a=copy.deepcopy(py); a["optimize"]=value; cases.append((self.m,a,"python")) # 5,6
        for field,value in (("source_sha256","d"*64),("architecture","arm64"),("options",["--jitless"])):
            a=copy.deepcopy(self.js); a[field]=value; cases.append(a) # 7-9
        for item in cases:
            m,a,l=(item if isinstance(item,tuple) else (self.m,item,"javascript"))
            self.assertFalse(compare_conditions(m,a,l)["exact_applicability"])
        # 10 order coverage is independently required by callers; invalid coverage is rejected.
        old=copy.deepcopy(self.m); old["measurement_order"]=["direct","function_call","direct"]
        self.assertTrue(validate_manifest_v2(old))
        # 11-13 old/missing values are readable by comparator, never inferred, never exact.
        legacy={"languages":{"javascript":{"runtime":self.m["languages"]["javascript"]["runtime"],"source":{"sha256":"a"*64},"options":[]}},"architecture":"x64"}
        result=compare_conditions(legacy,self.js,"javascript")
        self.assertEqual("missing",result["checks"]["v8"]); self.assertFalse(result["exact_applicability"])


if __name__ == "__main__": unittest.main()
