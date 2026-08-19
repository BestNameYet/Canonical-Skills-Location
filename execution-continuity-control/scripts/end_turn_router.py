#!/usr/bin/env python3
"""Deterministic Pre-END-TURN continuation questionnaire router.

The action questioner invokes this script only after AQ2 establishes that the
tracked action is an end-of-turn attempt. The model answers one router question
at a time. The script owns legal traversal and directive classification.

When a cycle reaches CONTINUE, COMPLETE, or IMPASSE, the router sends one
formatted ``router_cycle`` data object to ``action_event_recorder.py``. The
recorder appends that object to a new immutable execution-record snapshot.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

Q = {
"Q1":("Did any attempted tool, method, command, source, operation, or execution path fail, error, become unavailable, or produce less of the needed result than requested?",["YES","NO"]),
"Q1.1":("Does the observed evidence establish that the entire requested task is impossible, rather than merely that this particular path failed?",["YES","NO"]),
"Q1.2":("Was the actual cause of the failure inspected or established from observable evidence?",["YES","NO"]),
"Q2":("Is the proposed response about to say that a needed tool, capability, file, source, location, permission, operation, or execution route is unavailable, inaccessible, unsupported, or impossible?",["YES","NO"]),
"Q2.1":("Has that claimed limitation actually been tested or directly observed?",["YES","NO"]),
"Q2.2":("Does the observed limitation prevent the requested result, or only this particular way of producing it?",["ONLY_THIS_PATH","PREVENTS_RESULT"]),
"Q3":("Is execution stopping because some requirement, prerequisite, condition, format, dependency, approval, process step, certainty threshold, or other condition is said to be unmet?",["YES","NO"]),
"Q3.1":("Can the exact requirement be located in the user's request or an applicable higher-priority instruction?",["YES","NO"]),
"Q3.2":("Is there another legitimate way to satisfy that exact requirement?",["YES","NO","UNKNOWN"]),
"Q4":("Is the proposed response about to ask the user for permission, approval, confirmation, or authorization before continuing?",["YES","NO"]),
"Q4.1":("Does the user's existing request already authorize the proposed action?",["YES","NO"]),
"Q4.2":("Was applicable authorization already granted earlier and has it not been withdrawn or superseded?",["YES","NO"]),
"Q4.3":("Is new approval being sought only because the command wording, tool, subtask, execution context, or implementation changed while the authorized objective remained the same?",["YES","NO"]),
"Q4.4":("Can the exact rule requiring new authorization be located?",["YES","NO"]),
"Q5":("Is the proposed response about to ask the user a question, defer execution, or stop because information is missing, ambiguous, or uncertain?",["YES","NO"]),
"Q5.1":("Can the exact unknown value be identified?",["YES","NO"]),
"Q5.2":("Would materially different values of that unknown change the next useful action or the correctness of the requested result?",["YES","NO"]),
"Q5.3":("Can the value be resolved from the user's current request or already supplied context?",["YES","NO"]),
"Q5.4":("Can the value be retrieved or determined using an available tool, source, file, inspection, or calculation?",["YES","NO"]),
"Q5.5":("Can a reasonable non-destructive default or bounded assumption preserve useful progress?",["YES","NO"]),
"Q6":("Does the proposed response describe an action that could be performed now without actually performing it?",["YES","NO"]),
"Q6.1":("Did the user request the description or plan itself rather than execution of the action?",["YES","NO"]),
"Q7":("Does the proposed response mainly restate the user's request, summarize instructions, report status or progress, or present response-shaped text while the requested substantive action or result has not actually occurred?",["YES","NO"]),
"Q7.1":("Does the requested result depend on an observable operation, state change, retrieval, artifact, calculation, or other result beyond merely producing explanatory text?",["YES","NO"]),
"Q7.2":("Is there observable evidence that the required operation or result actually occurred?",["YES","NO"]),
"Q8":("Is any requested portion still unperformed even though it does not depend on the currently blocked, failed, or unresolved portion?",["YES","NO"]),
"Q9":("Is the proposed response acting from an earlier request, prior assumption, obsolete state, or previous task frame that conflicts with the user's latest applicable request or supplied information?",["YES","NO"]),
"Q9.1":("Is the newer applicable state already available in the conversation, tools, artifacts, or supplied context?",["YES","NO"]),
"Q10":("Is execution stopping, detouring, qualifying, or demanding resolution because of a premise, concern, interpretation, scope element, objective, or constraint introduced by the assistant?",["YES","NO"]),
"Q10.1":("Can the exact source of that premise, scope element, objective, or constraint be located in the user's request or governing instructions?",["YES","NO"]),
"Q10.2":("Is the model treating that legitimate element more broadly than its source requires?",["YES","NO"]),
"Q11":("Does an unmet requested result depend on an available tool or source that has not been successfully used while other tools, functions, sources, or response paths were selected instead?",["YES","NO"]),
"Q11.1":("Is that tool or source directly suited to the unmet requirement?",["YES","NO"]),
"Q12":("Does the proposed response move unfinished work into a later message, future turn, background process, promised follow-up, or autonomous continuation that has not actually been invoked?",["YES","NO"]),
"Q12.1":("Has a real mechanism capable of carrying out that future execution actually been invoked?",["YES","NO"]),
"Q13":("Is the proposed response delaying, gating, or performing unnecessary work because a non-execution request was interpreted as an instruction to perform the action being discussed?",["YES","NO"]),
"Q13.1":("Did the user actually request execution of that action?",["YES","NO"]),
"Q14":("Is planning, decomposition, logging, validation, formatting, approval, taxonomy construction, or another support process preventing substantive execution from continuing?",["YES","NO"]),
"Q14.1":("Can the exact requirement making that support process a prerequisite at this point be located in the user's request or higher-priority instructions?",["YES","NO"]),
"Q14.2":("Can the required support process be satisfied now without unnecessarily interrupting substantive execution?",["YES","NO"]),
"Q15":("Is there any other concrete reason the assistant is about to stop before the request has been carried as far as currently available information, authority, tools, and safe methods permit?",["YES","NO"]),
"Q15.1":("What observable fact makes further execution impossible or inappropriate? Answer NONE if no observable fact can be identified.",["FREE_TEXT_OR_NONE"]),
"Q15.2":("Has that fact been tested or verified where testing is available?",["YES","NO"]),
"Q15.3":("Can changing the execution path avoid the condition while preserving the requested result?",["YES","NO","UNKNOWN"]),
"A1":("Can the same result be produced by a different procedure or method?",["YES","NO"]),
"A2":("Can another available tool perform the required operation or provide the required result?",["YES","NO"]),
"A3":("Can the needed information or input be obtained from another available source?",["YES","NO"]),
"A4":("Can the input, intermediate state, or output be converted to another representation that an available path can use?",["YES","NO"]),
"A5":("Can the same operation be performed in another available location, environment, execution context, or storage surface?",["YES","NO"]),
"A6":("Can execution be reordered so another step can occur first, the blocked step can be bypassed temporarily, or a later independent result can unlock the path?",["YES","NO"]),
"A7":("Can the blocked operation be divided into smaller executable pieces?",["YES","NO"]),
"A8":("Can the blocking dependency be retrieved, derived, inferred, substituted, reconstructed, or legitimately eliminated?",["YES","NO"]),
"A9":("Is there any requested result or portion that does not depend on the blocked path?",["YES","NO"]),
"I1":("Can the exact unresolved requirement be located in the user's request or a higher-priority instruction?",["YES","NO"]),
"I2":("Is there observable evidence that the requirement currently cannot be satisfied?",["YES","NO"]),
"I3":("Have all applicable Alternative Path Search properties been tested or mechanically determined inapplicable?",["YES","NO"]),
"I4":("Does any independently executable requested work remain?",["YES","NO"]),
"I5":("Is there any currently available action that could still materially reduce the gap between the present state and the requested result?",["YES","NO"]),
"C1":("Can any explicit requested action, answer, output, modification, retrieval, evaluation, or deliverable be identified for which no corresponding produced result can be pointed to?",["YES","NO"]),
"C2":("Does any claimed completion depend on an operation, artifact, retrieval, calculation, state change, or tool result for which no observable supporting result exists?",["YES","NO"]),
"C3":("Does any requested portion remain only partially satisfied?",["YES","NO"]),
"C4":("Is the proposed response itself the requested result, or does it actually contain or provide the requested result or a usable reference to it?",["YES","NO"]),
}

ALT_NEXT={"A1":"A2","A2":"A3","A3":"A4","A4":"A5","A5":"A6","A6":"A7","A7":"A8","A8":"A9"}

CONTINUE_INSTRUCTIONS={
"Q1.2:NO":"Inspect the failure result, error, state, environment, or returned evidence. Do not infer a task-wide limitation from an unidentified cause.",
"Q2.1:NO":"Test the claimed capability or availability boundary using available tools, state, files, sources, permissions, or direct inspection.",
"Q3.1:NO":"Remove the unsupported requirement or prerequisite and continue execution without satisfying it.",
"Q3.2:YES":"Use the identified legitimate alternative method to satisfy the exact requirement now.",
"Q4.1:YES":"Continue without asking for authorization again.",
"Q4.2:YES":"Preserve the still-valid prior authorization and continue.",
"Q4.3:YES":"Do not narrow existing authorization merely because command wording, tool, subtask, execution context, or implementation changed. Continue.",
"Q4.4:NO":"Do not create a new authorization requirement. Continue under the authority already supplied.",
"Q5.1:NO":"No concrete information dependency has been established. Continue execution.",
"Q5.2:NO":"The uncertainty does not materially control execution. Continue without asking.",
"Q5.3:YES":"Resolve the value from the current request or already supplied context and continue.",
"Q5.4:YES":"Retrieve or determine the missing value with the available tool, source, file, inspection, or calculation.",
"Q5.5:YES":"Use a reasonable non-destructive default or bounded assumption and continue.",
"Q6.1:NO":"Perform the described available action now instead of reporting an intention, plan, or next step.",
"Q7.1:NO":"Answer the substantive request directly instead of substituting restatement or status.",
"Q7.2:YES":"Use and deliver the actual observable result rather than merely asserting that it occurred.",
"Q7.2:NO":"Perform the substantive operation and verify its result before proposing END_TURN again.",
"Q8:YES":"Perform every independently executable requested portion before ending the turn.",
"Q9.1:YES":"Re-anchor execution on the newest applicable state and redo affected work where necessary.",
"Q10.1:NO":"Drop the assistant-introduced premise, objective, constraint, or scope element and return to the user's task.",
"Q10.2:YES":"Narrow the legitimate element to exactly what its source requires and continue.",
"Q10.2:NO":"Handle only the portion actually required by the sourced premise or constraint and continue.",
"Q11.1:YES":"Use the directly suited tool or source now and inspect its result.",
"Q12.1:YES":"Report only what the real invoked future mechanism establishes and perform all other work possible now. If creating that mechanism was itself the complete request, prove completion on the next cycle.",
"Q12.1:NO":"Do not promise imaginary future execution. Perform everything executable in the current turn now.",
"Q13.1:NO":"Stop executing or imposing prerequisites for an unrequested action. Answer the request type actually made.",
"Q13.1:YES":"Treat the request as an execution request and continue the requested execution.",
"Q14.1:NO":"Stop treating the support process as a prerequisite and continue substantive execution.",
"Q14.2:YES":"Satisfy the genuinely required support process using the least interruptive route, then resume substantive execution.",
"Q15.1:NONE":"No observable fact supports stopping. Continue execution.",
"Q15.2:NO":"Test or verify the asserted stopping fact where testing is available.",
"A1:YES":"Execute the alternative procedure or method that preserves the same required result.",
"A2:YES":"Use the alternative available tool that can perform the required operation or provide the required result.",
"A3:YES":"Obtain the needed information or input from the alternative available source and continue.",
"A4:YES":"Convert the input, intermediate state, or output to the usable alternative representation and execute through it.",
"A5:YES":"Use the alternative available location, environment, execution context, or storage surface.",
"A6:YES":"Reorder execution as identified and continue through the newly available sequence.",
"A7:YES":"Divide the blocked operation into smaller executable pieces, execute the achievable pieces, and reassess.",
"A8:YES":"Resolve, replace, derive, infer, reconstruct, or legitimately eliminate the blocking dependency and continue.",
"A9:YES":"Perform every requested result or portion that does not depend on the blocked path.",
"I1:NO":"Remove the unresolved condition because it cannot be located in the user's request or a higher-priority instruction.",
"I2:NO":"Establish or test the alleged blocker before treating it as an impasse.",
"I4:YES":"Perform all independently executable requested work before treating the remaining dependency as an impasse.",
"I5:YES":"Perform the available action that materially reduces the gap between the current state and the requested result.",
"C1:YES":"Perform the explicit requested action, answer, output, modification, retrieval, evaluation, or deliverable that lacks a produced result.",
"C2:YES":"Perform or verify the operation, artifact, retrieval, calculation, state change, or tool result needed to support the claimed completion.",
"C3:YES":"Complete the partially satisfied requested portion, or route its concrete obstruction through the applicable failure branch on the next cycle.",
"C4:NO":"Deliver the actual requested result or a usable reference to it before proposing END_TURN again.",
}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00","Z")


def write_json(path: Path, obj: Any):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=str(path.parent))
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            json.dump(obj,f,indent=2,ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def validate_state(s):
    if not isinstance(s,dict):
        raise SystemExit("Router state must be a JSON object")
    if not isinstance(s.get("cycle_id"),str) or not s["cycle_id"]:
        raise SystemExit("Router state has invalid cycle_id")
    if not isinstance(s.get("trace"),list):
        raise SystemExit("Router state has invalid trace")
    status=s.get("status")
    if status not in {"QUESTION","CONTINUE","COMPLETE","IMPASSE"}:
        raise SystemExit("Router state has invalid status")
    if status=="QUESTION" and s.get("current") not in Q:
        raise SystemExit("Router state has invalid current question")
    return s


def load(path):
    if not path.exists():
        raise SystemExit(f"State file does not exist: {path}")
    return validate_state(json.loads(path.read_text(encoding="utf-8")))


def norm(qid,raw):
    raw=raw.strip()
    if qid=="Q15.1":
        return "NONE" if raw.upper() in {"NONE","NO FACT","NO_OBSERVABLE_FACT"} else raw
    k=raw.upper().strip()
    aliases={"Y":"YES","N":"NO","ONLY THIS PATH":"ONLY_THIS_PATH","THIS PATH":"ONLY_THIS_PATH","PATH ONLY":"ONLY_THIS_PATH","PREVENTS RESULT":"PREVENTS_RESULT","TASK WIDE":"PREVENTS_RESULT","TASK-WIDE":"PREVENTS_RESULT","UNSURE":"UNKNOWN","DON'T KNOW":"UNKNOWN","DONT KNOW":"UNKNOWN"}
    return aliases.get(k,k)


def compact(trace):
    out=[]
    for x in trace:
        if x["kind"]=="answer":
            a=x["answer"]
            a="<OBSERVABLE_FACT>" if x["question_id"]=="Q15.1" and a!="NONE" else a
            out.append(f"{x['question_id']}:{a}")
        else:
            out.append(f"{x['directive']}: {x.get('instruction','')}".rstrip(": "))
    return " → ".join(out)


def payload_q(s):
    qid=s["current"]
    text,allowed=Q[qid]
    return {"status":"QUESTION","state":s["state_path"],"cycle_id":s["cycle_id"],"question_id":qid,"question":text,"allowed_answers":allowed,"trace":s["trace"],"trace_compact":compact(s["trace"])}


def goto(s,qid):
    s["current"]=qid
    s["status"]="QUESTION"
    s["updated_at"]=now()
    return payload_q(s)


def run_json(command: list[str]) -> dict[str, Any]:
    completed=subprocess.run(command,capture_output=True,text=True)
    stdout=completed.stdout.strip()
    if not stdout:
        raise RuntimeError(f"recorder produced no JSON; stderr={completed.stderr.strip()!r}")
    try:
        data=json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"recorder produced invalid JSON: {stdout!r}") from exc
    if completed.returncode!=0:
        raise RuntimeError(f"recorder failed: {data!r}")
    return data


def send_cycle_to_recorder(s):
    pairs=[]
    for item in s["trace"]:
        if item.get("kind")!="answer":
            continue
        qid=item["question_id"]
        pairs.append({"id":qid,"question":Q[qid][0],"answer":item["answer"]})
    payload={
        "action_type":"router_cycle",
        "scope":s["scope"],
        "pairs":pairs,
        "directive":s["directive"],
    }
    if s["directive"]=="CONTINUE":
        payload["instruction"]=s["instruction"]
    if s["directive"]=="IMPASSE":
        payload["impasse_evidence"]=s.get("impasse_evidence") or "No additional impasse evidence was captured beyond the recorded router answers."
    if s.get("source"):
        payload["source"]=s["source"]
    payload_path=Path(s["state_path"]).with_suffix(".action.json")
    write_json(payload_path,payload)
    command=[
        sys.executable,s["recorder"],"append",
        "--output-dir",s["output_dir"],
        "--record",s["record"],
        "--record-name",s["record_name"],
        "--record-id",s["record_id"],
        "--action-file",str(payload_path),
    ]
    return run_json(command)


def directive(s,d,instruction,evidence=None):
    s["trace"].append({"kind":"directive","directive":d,"instruction":instruction})
    s["status"]=d
    s["directive"]=d
    s["instruction"]=instruction
    s["current"]=None
    s["updated_at"]=now()
    s["completed_at"]=now()
    if evidence:
        s["impasse_evidence"]=evidence
    receipt=send_cycle_to_recorder(s)
    s["record_receipt"]=receipt
    s["record"]=receipt["record"]
    s["record_name"]=receipt["record_filename"]
    write_json(Path(s["state_path"]),s)
    return {"status":"DIRECTIVE","state":s["state_path"],"cycle_id":s["cycle_id"],"directive":d,"terminal":d in {"COMPLETE","IMPASSE"},"end_turn_permitted":d in {"COMPLETE","IMPASSE"},"instruction":instruction,"trace":s["trace"],"trace_compact":compact(s["trace"]),"record":receipt}


def cont(s,key):
    return directive(s,"CONTINUE",CONTINUE_INSTRUCTIONS[key])


def transition(s,qid,a):
    key=f"{qid}:{a}"
    if key in CONTINUE_INSTRUCTIONS:
        return cont(s,key)
    routes={
      ("Q1","YES"):"Q1.1",("Q1","NO"):"Q2",("Q1.1","YES"):"Q1.2",("Q1.1","NO"):"A1",("Q1.2","YES"):"A1",
      ("Q2","YES"):"Q2.1",("Q2","NO"):"Q3",("Q2.1","YES"):"Q2.2",("Q2.2","ONLY_THIS_PATH"):"A1",("Q2.2","PREVENTS_RESULT"):"A1",
      ("Q3","YES"):"Q3.1",("Q3","NO"):"Q4",("Q3.1","YES"):"Q3.2",("Q3.2","NO"):"A1",("Q3.2","UNKNOWN"):"A1",
      ("Q4","YES"):"Q4.1",("Q4","NO"):"Q5",("Q4.1","NO"):"Q4.2",("Q4.2","NO"):"Q4.3",("Q4.3","NO"):"Q4.4",("Q4.4","YES"):"I1",
      ("Q5","YES"):"Q5.1",("Q5","NO"):"Q6",("Q5.1","YES"):"Q5.2",("Q5.2","YES"):"Q5.3",("Q5.3","NO"):"Q5.4",("Q5.4","NO"):"Q5.5",("Q5.5","NO"):"I1",
      ("Q6","YES"):"Q6.1",("Q6","NO"):"Q7",("Q6.1","YES"):"Q7",
      ("Q7","YES"):"Q7.1",("Q7","NO"):"Q8",("Q7.1","YES"):"Q7.2",
      ("Q8","NO"):"Q9",
      ("Q9","YES"):"Q9.1",("Q9","NO"):"Q10",("Q9.1","NO"):"Q5",
      ("Q10","YES"):"Q10.1",("Q10","NO"):"Q11",("Q10.1","YES"):"Q10.2",
      ("Q11","YES"):"Q11.1",("Q11","NO"):"Q12",("Q11.1","NO"):"A1",
      ("Q12","YES"):"Q12.1",("Q12","NO"):"Q13",
      ("Q13","YES"):"Q13.1",("Q13","NO"):"Q14",
      ("Q14","YES"):"Q14.1",("Q14","NO"):"Q15",("Q14.1","YES"):"Q14.2",("Q14.2","NO"):"A1",
      ("Q15","YES"):"Q15.1",("Q15","NO"):"C1",("Q15.2","YES"):"Q15.3",("Q15.3","YES"):"A1",("Q15.3","UNKNOWN"):"A1",("Q15.3","NO"):"I1",
      ("I1","YES"):"I2",("I2","YES"):"I3",("I3","NO"):"A1",("I3","YES"):"I4",("I4","NO"):"I5",
      ("C1","NO"):"C2",("C2","NO"):"C3",("C3","NO"):"C4",
    }
    if qid=="Q15.1" and a!="NONE":
        s["observable_stopping_fact"]=a
        return goto(s,"Q15.2")
    if (qid,a) in routes:
        return goto(s,routes[(qid,a)])
    if qid in ALT_NEXT and a=="NO":
        return goto(s,ALT_NEXT[qid])
    if qid=="A9" and a=="NO":
        return goto(s,"I1")
    if qid=="I5" and a=="NO":
        return directive(s,"IMPASSE","A required dependency remains unsatisfied; applicable alternatives are exhausted; no independent requested work or other available gap-reducing action remains. Report the specific surviving blocker and completed useful work.",s.get("observable_stopping_fact"))
    if qid=="C4" and a=="YES":
        return directive(s,"COMPLETE","The questionnaire found no remaining continuation trigger and the Completion Evidence Test is satisfied. END_TURN is permitted.")
    raise RuntimeError(f"Unhandled transition {qid} / {a}")


def validate(qid,a):
    allowed=Q[qid][1]
    if allowed==["FREE_TEXT_OR_NONE"]:
        if not a.strip():
            raise ValueError("Q15.1 requires a non-empty observable fact or NONE")
    elif a not in allowed:
        raise ValueError(f"Invalid answer {a!r}; allowed: {allowed}")


def cmd_start(args):
    p=Path(args.state)
    if p.exists() and not args.force:
        s=load(p)
        if s.get("status")=="QUESTION":
            print(json.dumps({"error":"ACTIVE_CYCLE_EXISTS","cycle_id":s["cycle_id"],"current":s["current"]},indent=2))
            return 2
    source={}
    if args.chat_id is not None:
        source["chat_id"]=args.chat_id
    if args.chat_title is not None:
        source["chat_title"]=args.chat_title
    s={
        "cycle_id":args.cycle_id or str(uuid.uuid4()),
        "started_at":now(),
        "updated_at":now(),
        "status":"QUESTION",
        "current":"Q1",
        "trace":[],
        "state_path":str(p),
        "scope":args.scope,
        "recorder":args.recorder,
        "output_dir":args.output_dir,
        "record":args.record,
        "record_name":args.record_name,
        "record_id":args.record_id,
        "source":source,
    }
    write_json(p,s)
    print(json.dumps(payload_q(s),indent=2,ensure_ascii=False))
    return 0


def cmd_answer(args):
    p=Path(args.state)
    s=load(p)
    if s.get("status")!="QUESTION" or not s.get("current"):
        print(json.dumps({"error":"CYCLE_NOT_WAITING_FOR_ANSWER","status":s.get("status"),"directive":s.get("directive")},indent=2))
        return 2
    qid=s["current"]
    a=norm(qid,args.answer)
    try:
        validate(qid,a)
    except ValueError as e:
        print(json.dumps({"error":"INVALID_ANSWER","question_id":qid,"question":Q[qid][0],"allowed_answers":Q[qid][1],"received":args.answer,"message":str(e)},indent=2,ensure_ascii=False))
        return 2
    s["trace"].append({"kind":"answer","question_id":qid,"answer":a})
    result=transition(s,qid,a)
    if s.get("status")=="QUESTION":
        write_json(p,s)
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0


def cmd_show(args):
    s=load(Path(args.state))
    if s.get("status")=="QUESTION":
        out=payload_q(s)
    else:
        out={"status":"DIRECTIVE","state":s["state_path"],"cycle_id":s["cycle_id"],"directive":s.get("directive"),"end_turn_permitted":s.get("directive") in {"COMPLETE","IMPASSE"},"instruction":s.get("instruction"),"trace":s.get("trace",[]),"trace_compact":compact(s.get("trace",[])),"record":s.get("record_receipt")}
    print(json.dumps(out,indent=2,ensure_ascii=False))
    return 0


def cmd_reset(args):
    p=Path(args.state)
    if p.exists():
        p.unlink()
    print(json.dumps({"status":"RESET","state":str(p)},indent=2))
    return 0


def main():
    ap=argparse.ArgumentParser()
    sub=ap.add_subparsers(dest="cmd",required=True)
    p=sub.add_parser("start")
    p.add_argument("--state",required=True)
    p.add_argument("--scope",required=True,choices=["worker","orchestrator"])
    p.add_argument("--recorder",required=True)
    p.add_argument("--output-dir",required=True)
    p.add_argument("--record",required=True)
    p.add_argument("--record-name",required=True)
    p.add_argument("--record-id",required=True)
    p.add_argument("--chat-id")
    p.add_argument("--chat-title")
    p.add_argument("--cycle-id")
    p.add_argument("--force",action="store_true")
    p.set_defaults(fn=cmd_start)
    p=sub.add_parser("answer"); p.add_argument("--state",required=True); p.add_argument("--answer",required=True); p.set_defaults(fn=cmd_answer)
    p=sub.add_parser("show"); p.add_argument("--state",required=True); p.set_defaults(fn=cmd_show)
    p=sub.add_parser("reset"); p.add_argument("--state",required=True); p.set_defaults(fn=cmd_reset)
    a=ap.parse_args()
    try:
        return a.fn(a)
    except Exception as exc:
        print(json.dumps({"status":"FAIL","code":type(exc).__name__,"detail":str(exc)},ensure_ascii=False))
        return 2


if __name__=="__main__":
    sys.exit(main())
