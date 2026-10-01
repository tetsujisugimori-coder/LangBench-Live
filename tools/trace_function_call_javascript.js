#!/usr/bin/env node
"use strict";

const { traceStimulus } = require("../benchmarks/function_call_numeric_sum/javascript/main.js");

const order = process.argv[2];
if (!order) throw new Error("trace order is required");
traceStimulus(order);
