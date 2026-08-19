#!/usr/bin/env python3
"""Single-file Execution Continuity Control runtime."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CONTROL_VERSION = 4
PAYLOAD_SCHEMA = "execution-continuity-payload-v4"
INITIALIZATION_SCHEMA = "execution-continuity-initialization-v1"
PREPROCESSOR_PROTOCOL = "prompt-preprocessor-v1"
RECORD_PREFIX = "execution-record_"
RECORD_SUFFIX = ".json"
STAMP_RE = re.compile(r"^execution-record_(\d{8}T\d{12}Z)\.json$")
SCOPES = {"worker", "orchestrator"}
DIRECTIVES = {"CONTINUE", "COMPLETE", "IMPASSE"}

BEHAVIORAL_INSTRUCTIONS = [
    "The generated bundle is the sole Orchestrator. Act as the Worker only under the current payload.",
    "NO CURRENT PAYLOAD = NO EXECUTION AUTHORITY.",
    "The model-facing task_prompt is the governing task statement for this turn.",
    "TASK_ACTION authorizes exactly one material task action toward task_prompt.",
    "After the commanded action completes, fails, or reaches an attempted end-of-turn stop point, return the complete prior payload unchanged to this same bundle before any further material task action.",
    "During bundle protocol questions, answer only the question asked. Protocol answering grants no substantive task authority.",
    "FINAL_RESPONSE authorizes only construction and delivery of the final user-facing response.",
    "Planning, status reporting, procedural compliance, or statements of intention do not substitute for requested execution when execution is available.",
    "Use observable execution evidence for completion, mutation, persistence, retrieval, validation, and failure claims.",
]

ACTION_SUBTYPES = {
    "ACQUIRE": {"READ", "SEARCH", "RETRIEVE"},
    "TRANSFORM": {"CALCULATE", "DECOMPOSE", "SYNTHESIZE", "CONVERT", "EXTRACT"},
    "EVALUATE": {"COMPARE", "CLASSIFY", "VALIDATE", "SCORE"},
    "DECIDE": {"SELECT", "REJECT", "PRIORITIZE", "DEFER"},
    "ACT": {"CREATE", "MODIFY", "DELETE", "EXECUTE", "CALL"},
    "OBSERVE": {"INSPECT", "RECEIVE", "DETECT_ERROR", "DETECT_CHANGE"},
    "COMMUNICATE": {"ASK", "RETURN", "REPORT", "INSTRUCT", "SIGNAL"},
}

ACTION_ONTOLOGY_DESCRIPTIONS = {
    "ACQUIRE": (
        "obtain information or inputs",
        {
            "READ": "read content already available to the Worker",
            "SEARCH": "look for relevant information among possible sources or locations",
            "RETRIEVE": "fetch a specifically identified source, object, file, or result",
        },
    ),
    "TRANSFORM": (
        "derive a new representation or result from available inputs",
        {
            "CALCULATE": "compute a numeric or formal result",
            "DECOMPOSE": "split a whole into meaningful component parts",
            "SYNTHESIZE": "combine inputs into a new integrated result",
            "CONVERT": "change representation, format, units, or encoding",
            "EXTRACT": "isolate requested information from a larger input",
        },
    ),
    "EVALUATE": (
        "assess information, alternatives, or results without itself committing to an option",
        {
            "COMPARE": "assess similarities, differences, or relative properties",
            "CLASSIFY": "assign an item to a defined category",
            "VALIDATE": "determine whether an item satisfies a requirement or criterion",
            "SCORE": "assign a value or ranking under a stated measure",
        },
    ),
    "DECIDE": (
        "commit to a choice that controls subsequent execution",
        {
            "SELECT": "choose one available alternative for subsequent use",
            "REJECT": "exclude an alternative from subsequent use",
            "PRIORITIZE": "establish relative execution preference or order",
            "DEFER": "intentionally postpone an otherwise available alternative",
        },
    ),
    "ACT": (
        "perform an operation that changes state or invokes executable behavior",
        {
            "CREATE": "create a new artifact, object, or persistent state",
            "MODIFY": "change an existing artifact, object, or persistent state",
            "DELETE": "remove an existing artifact, object, or persistent state",
            "EXECUTE": "run executable logic, a command, or a procedure",
            "CALL": "invoke an external tool, function, service, or operation",
        },
    ),
    "OBSERVE": (
        "inspect or receive state without intentionally changing it",
        {
            "INSPECT": "examine an existing state, artifact, or result",
            "RECEIVE": "accept information or output delivered by another process or source",
            "DETECT_ERROR": "observe that an attempted operation failed or produced an error",
            "DETECT_CHANGE": "observe that state differs from an earlier state",
        },
    ),
    "COMMUNICATE": (
        "exchange information with the user or another process",
        {
            "ASK": "request information needed from another party",
            "RETURN": "provide a requested result or value",
            "REPORT": "communicate an observed state, finding, or outcome",
            "INSTRUCT": "communicate directions for an action",
            "SIGNAL": "emit a protocol or control indication",
        },
    ),
}

def action_ontology_text() -> str:
    groups = []
    for action_type, (type_description, subtypes) in ACTION_ONTOLOGY_DESCRIPTIONS.items():
        subtype_text = "; ".join(f"{subtype} — {description}" for subtype, description in subtypes.items())
        groups.append(f"{action_type} — {type_description}: {subtype_text}")
    return " | ".join(groups)

ACTION_ONTOLOGY_TEXT = action_ontology_text()
INTENT_RELATIONS = {"DIRECT", "SUPPORTING", "NONE", "OBSTRUCTED"}
EVIDENCE_TYPES = {"TOOL_RESULT", "ARTIFACT_STATE", "EXTERNAL_SOURCE", "COMPUTED_RESULT", "EXECUTION_RESULT", "USER_VISIBLE_OUTPUT", "MODEL_OBSERVATION", "NONE"}
INTENT_OUTCOMES = {"SUCCESS", "PARTIAL", "FAILED", "UNADDRESSED", "NOT_APPLICABLE"}
PLAN_RELATIONSHIPS = {"NO_PRIOR_PLAN", "MATCHED", "PARTIAL_DIVERGENCE", "MAJOR_DIVERGENCE"}
DIVERGENCE_CAUSES = {"TOOL_RESULT", "TOOL_FAILURE", "NEW_INFORMATION", "DEPENDENCY", "USER_CONSTRAINT", "SYSTEM_CONSTRAINT", "CANONICAL_RULE", "AVAILABILITY", "VALIDATION_FAILURE", "EFFICIENCY", "OTHER"}
DECISION_BASES = {"USER_EXPLICITLY_REQUIRED", "REQUIRED_SUBGOAL", "PRIOR_PLAN", "OBSERVED_STATE", "TOOL_AVAILABILITY", "DEPENDENCY_ORDER", "FAILURE_RECOVERY", "VALIDATION_REQUIREMENT", "CANONICAL_RULE", "EFFICIENCY", "ONLY_VIABLE_PATH", "OTHER"}
OVERALL_OUTCOMES = {"COMPLETE_SUCCESS", "PARTIAL_SUCCESS", "FAILED", "BLOCKED", "NO_EFFECT"}
NARRATIVE_HEADINGS = ["NARRATIVE_MAPPING", "INTENT:", "ACTION_PATH:", "PLAN_RELATION:", "OUTCOME_MAPPING:", "DECISION_CONTEXT:"]

ACTION_QUESTIONS = [
    {"id":"AQ1","question":"Is this action an end-of-turn attempt? Answer YES or NO.","format":"ENUM: YES | NO","allowed_answers":["YES","NO"]},
    {"id":"AQ2","question":"State the user intent this action was intended to advance as one concise sentence describing the requested end state.","format":"SHORT_TEXT"},
    {"id":"AQ3","question":"Decompose that user intent into a numbered list of independently testable requirements. Answer as a JSON array of {id,text} objects using UI1, UI2, ... in order.","format":"JSON_ARRAY"},
    {"id":"AQ4","question":f"Decompose the completed activity into the smallest meaningful ordered action units. Answer as a JSON array of {{id,type,subtype,target}} objects using A1, A2, ... in order. Choose type/subtype only from these enumerated choices, using the accompanying natural-language descriptors: {ACTION_ONTOLOGY_TEXT}","format":"JSON_ARRAY"},
    {"id":"AQ5","question":"Did an explicit plan for this activity exist before execution of the recorded activity began? Answer YES or NO.","format":"ENUM: YES | NO","allowed_answers":["YES","NO"]},
    {"id":"AQ6","question":"Record the prior plan if one existed. Answer as a JSON array of {id,text} objects using P1, P2, ... in order; answer [] when AQ5 is NO.","format":"JSON_ARRAY"},
    {"id":"AQ7","question":"Map each atomic action to the decomposed user-intent items. Answer as a JSON array of {action_id,intent_ids,relation} objects using only existing A# and UI# IDs.","format":"JSON_ARRAY"},
    {"id":"AQ8","question":"Catalog the observable evidence for this activity. Answer as a JSON array of {id,type,reference} objects using E1, E2, ... in order. Use [] only when no evidence is available.","format":"JSON_ARRAY"},
    {"id":"AQ9","question":"Evaluate every decomposed user-intent item. Answer as a JSON array of {intent_id,result,action_ids,evidence_ids,remaining_gap} objects using only existing IDs.","format":"JSON_ARRAY"},
    {"id":"AQ10","question":"Compare the prior plan with the actual action path. Answer as a JSON object with relationship and divergences. When AQ5 is NO use NO_PRIOR_PLAN and [].","format":"JSON_OBJECT"},
    {"id":"AQ11","question":"For each material decision point, record why the next action was selected. Answer as a JSON array of {action_id,basis,note} objects. Use [] only when no discretionary decision point occurred.","format":"JSON_ARRAY"},
    {"id":"AQ12","question":"Classify the overall outcome of the recorded activity.","format":"ENUM","allowed_answers":sorted(OVERALL_OUTCOMES)},
    {"id":"AQ13","question":f"Record any decision-boundary counterfactuals that are actually supported by the observed state. Answer as a JSON array of {{condition,alternate_action_type,alternate_action_subtype,note}}. Choose alternate_action_type/alternate_action_subtype only from these enumerated choices, using the accompanying natural-language descriptors: {ACTION_ONTOLOGY_TEXT} Use [] when none is supported.","format":"JSON_ARRAY"},
    {"id":"AQ14","question":"Provide the required NARRATIVE_MAPPING note using headings NARRATIVE_MAPPING, INTENT:, ACTION_PATH:, PLAN_RELATION:, OUTCOME_MAPPING:, and DECISION_CONTEXT:. Reference existing UI#, A#, P#, and E# identifiers where applicable.","format":"FORMATTED_TEXT"},
]

ROUTER_Q = {
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

ALT_NEXT={"A1":"A2","A2":"A3","A3":"A4","A4":"A5","A5":"A6","A6":"A7","A7":"A8","A8":"A9","A9":"I1"}

# --- record functions -----------------------------------------------------

def utc_now()->datetime: return datetime.now(timezone.utc)
def iso_utc(dt:datetime|None=None)->str: return (dt or utc_now()).isoformat().replace("+00:00","Z")
def compact_stamp(dt:datetime|None=None)->str: return (dt or utc_now()).strftime("%Y%m%dT%H%M%S%fZ")
def canonical_json(obj:Any)->str: return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def sha256_json(obj:Any)->str: return hashlib.sha256(canonical_json(obj).encode()).hexdigest()
def read_json(path:Path)->dict[str,Any]: return json.loads(path.read_text(encoding="utf-8"))
def write_json_atomic(path:Path,data:dict[str,Any])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+".tmp")
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    temp.replace(path)

def runtime_record_dir() -> Path:
    configured = os.environ.get("EXECUTION_CONTINUITY_RECORD_DIR")
    if configured:
        return Path(configured)
    base = Path("/mnt/data")
    if base.exists() and os.access(base, os.W_OK):
        return base
    return Path.cwd()

def list_records(directory:Path)->list[tuple[datetime,Path]]:
    if not directory.exists(): return []
    found=[]
    for p in directory.iterdir():
        if not p.is_file(): continue
        m=STAMP_RE.fullmatch(p.name)
        if not m: continue
        try: found.append((datetime.strptime(m.group(1),"%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc),p))
        except ValueError: pass
    return sorted(found,key=lambda x:x[0])

def record_create(directory:Path)->Path:
    directory.mkdir(parents=True,exist_ok=True)
    path=directory/f"{RECORD_PREFIX}{compact_stamp()}{RECORD_SUFFIX}"
    while path.exists(): path=directory/f"{RECORD_PREFIX}{compact_stamp(utc_now()+timedelta(microseconds=1))}{RECORD_SUFFIX}"
    write_json_atomic(path,{"schema":"execution-continuity-record-v1","created_at":iso_utc(),"updated_at":iso_utc(),"last_sequence":0,"actions":[]})
    return path

def record_latest(directory:Path)->dict[str,Any]:
    recs=list_records(directory)
    path=recs[-1][1] if recs else record_create(directory)
    data=read_json(path)
    return {"record":str(path),"record_name":path.name,"action_count":int(data.get("last_sequence",0))}

def record_append(state:dict[str,Any],action:dict[str,Any])->dict[str,Any]:
    path=Path(state["record"]); data=read_json(path)
    seq=int(data.get("last_sequence",0))+1
    item={"sequence":seq,"timestamp":iso_utc(),**action}
    data.setdefault("actions",[]).append(item); data["last_sequence"]=seq; data["updated_at"]=iso_utc()
    write_json_atomic(path,data); state["action_count"]=seq
    return item

def record_read(path:Path)->dict[str,Any]: return read_json(path)

# --- validators/questionnaire --------------------------------------------

def require_text(v:Any,name:str)->str:
    if not isinstance(v,str) or not v.strip(): raise ValueError(f"{name} must be non-empty text")
    return v.strip()
def require_ids(seq:Any,prefix:str,name:str)->list[str]:
    if not isinstance(seq,list): raise ValueError(f"{name} must be array")
    out=[]
    for x in seq:
        if not isinstance(x,str) or not re.fullmatch(rf"{prefix}\d+",x): raise ValueError(f"{name} has invalid id")
        out.append(x)
    return out

def ask_json(question:dict[str,Any],validator=None)->Any:
    prompt={"protocol":"action-questionnaire","question_id":question["id"],"question":question["question"],"format":question.get("format"),"allowed_answers":question.get("allowed_answers")}
    while True:
        print(json.dumps(prompt,ensure_ascii=False),flush=True)
        line=sys.stdin.readline()
        if line=="": raise EOFError(f"EOF waiting for {question['id']}")
        raw=line.strip()
        if question.get("format","").startswith("ENUM"):
            value=raw
        else:
            try: value=json.loads(raw)
            except json.JSONDecodeError:
                value=raw
        try:
            if validator: validator(value)
            return value
        except Exception as exc:
            prompt={**prompt,"validation_error":str(exc)}


def validate_action_questionnaire(ans:dict[str,Any])->None:
    if ans["AQ1"] not in {"YES","NO"}: raise ValueError("AQ1")
    require_text(ans["AQ2"],"AQ2")
    reqs=ans["AQ3"]
    if not isinstance(reqs,list) or not reqs: raise ValueError("AQ3")
    ui_ids=[]
    for i,o in enumerate(reqs,1):
        if not isinstance(o,dict) or set(o)!={"id","text"} or o["id"]!=f"UI{i}": raise ValueError("AQ3 IDs")
        require_text(o["text"],"AQ3 text"); ui_ids.append(o["id"])
    acts=ans["AQ4"]
    if not isinstance(acts,list) or not acts: raise ValueError("AQ4")
    a_ids=[]
    for i,o in enumerate(acts,1):
        if not isinstance(o,dict) or set(o)!={"id","type","subtype","target"} or o["id"]!=f"A{i}": raise ValueError("AQ4 IDs")
        if o["type"] not in ACTION_SUBTYPES or o["subtype"] not in ACTION_SUBTYPES[o["type"]]: raise ValueError("AQ4 ontology")
        require_text(o["target"],"AQ4 target"); a_ids.append(o["id"])
    if ans["AQ5"] not in {"YES","NO"}: raise ValueError("AQ5")
    plans=ans["AQ6"]
    if not isinstance(plans,list): raise ValueError("AQ6")
    if ans["AQ5"]=="NO" and plans: raise ValueError("AQ6 must []")
    for i,o in enumerate(plans,1):
        if not isinstance(o,dict) or set(o)!={"id","text"} or o["id"]!=f"P{i}": raise ValueError("AQ6 IDs")
    maps=ans["AQ7"]
    if not isinstance(maps,list): raise ValueError("AQ7")
    for o in maps:
        if not isinstance(o,dict) or set(o)!={"action_id","intent_ids","relation"} or o["action_id"] not in a_ids or o["relation"] not in INTENT_RELATIONS: raise ValueError("AQ7")
        if any(x not in ui_ids for x in o["intent_ids"]): raise ValueError("AQ7 intents")
    ev=ans["AQ8"]
    if not isinstance(ev,list): raise ValueError("AQ8")
    e_ids=[]
    for i,o in enumerate(ev,1):
        if not isinstance(o,dict) or set(o)!={"id","type","reference"} or o["id"]!=f"E{i}" or o["type"] not in EVIDENCE_TYPES: raise ValueError("AQ8")
        e_ids.append(o["id"])
    outcomes=ans["AQ9"]
    if not isinstance(outcomes,list) or {o.get("intent_id") for o in outcomes if isinstance(o,dict)}!=set(ui_ids): raise ValueError("AQ9 coverage")
    for o in outcomes:
        if set(o)!={"intent_id","result","action_ids","evidence_ids","remaining_gap"} or o["result"] not in INTENT_OUTCOMES: raise ValueError("AQ9")
        if any(x not in a_ids for x in o["action_ids"]) or any(x not in e_ids for x in o["evidence_ids"]): raise ValueError("AQ9 refs")
    pr=ans["AQ10"]
    if not isinstance(pr,dict) or set(pr)!={"relationship","divergences"} or pr["relationship"] not in PLAN_RELATIONSHIPS or not isinstance(pr["divergences"],list): raise ValueError("AQ10")
    for d in pr["divergences"]:
        if not isinstance(d,dict) or set(d)!={"planned_step_id","actual_action_ids","cause","note"} or d["cause"] not in DIVERGENCE_CAUSES: raise ValueError("AQ10 divergence")
    dec=ans["AQ11"]
    if not isinstance(dec,list): raise ValueError("AQ11")
    for d in dec:
        if not isinstance(d,dict) or set(d)!={"action_id","basis","note"} or d["action_id"] not in a_ids or d["basis"] not in DECISION_BASES: raise ValueError("AQ11")
    if ans["AQ12"] not in OVERALL_OUTCOMES: raise ValueError("AQ12")
    cf=ans["AQ13"]
    if not isinstance(cf,list): raise ValueError("AQ13")
    for c in cf:
        if not isinstance(c,dict) or set(c)!={"condition","alternate_action_type","alternate_action_subtype","note"}: raise ValueError("AQ13")
        t,s=c["alternate_action_type"],c["alternate_action_subtype"]
        if t not in ACTION_SUBTYPES or s not in ACTION_SUBTYPES[t]: raise ValueError("AQ13 ontology")
    note=ans["AQ14"]
    if not isinstance(note,str): raise ValueError("AQ14")
    pos=-1
    for h in NARRATIVE_HEADINGS:
        n=note.find(h,pos+1)
        if n<0: raise ValueError("AQ14 headings invalid")
        pos=n


def run_action_questionnaire()->dict[str,Any]:
    ans={}
    for q in ACTION_QUESTIONS:
        qid=q["id"]
        def validator(v,q=q,qid=qid):
            if q.get("allowed_answers") and v not in q["allowed_answers"]: raise ValueError(f"{qid} invalid enum")
        ans[qid]=ask_json(q,validator)
    validate_action_questionnaire(ans)
    action={"action_type":"action_questionnaire","scope":"worker","answers":ans}
    return {"action":action,"state":{"answers":ans}}

# --- router ---------------------------------------------------------------

def ask_router(qid:str,pairs:list[dict[str,Any]])->str:
    text,allowed=ROUTER_Q[qid]
    while True:
        print(json.dumps({"protocol":"end-turn-router","question_id":qid,"question":text,"allowed_answers":allowed},ensure_ascii=False),flush=True)
        line=sys.stdin.readline()
        if line=="": raise EOFError(qid)
        ans=line.strip()
        if allowed==["FREE_TEXT_OR_NONE"] or ans in allowed:
            pairs.append({"question_id":qid,"question":text,"answer":ans}); return ans
        print(json.dumps({"validation_error":f"Allowed: {allowed}"}),flush=True)

def run_alt(pairs):
    q="A1"
    while q in ALT_NEXT:
        if ask_router(q,pairs)=="YES": return ("CONTINUE",f"Use the alternative path established by {q} and continue execution.")
        q=ALT_NEXT[q]
    return None

def run_impasse(pairs):
    if ask_router("I1",pairs)!="YES": return ("CONTINUE","The claimed unresolved requirement is not grounded; continue without treating it as a blocker.")
    if ask_router("I2",pairs)!="YES": return ("CONTINUE","The claimed inability is not evidenced; continue execution and test an available path.")
    if ask_router("I3",pairs)!="YES": return ("CONTINUE","Alternative path search is incomplete; continue by testing remaining applicable alternatives.")
    if ask_router("I4",pairs)=="YES": return ("CONTINUE","Independent requested work remains; continue with it now.")
    if ask_router("I5",pairs)=="YES": return ("CONTINUE","A currently available gap-reducing action remains; perform it now.")
    return ("IMPASSE",None)

def run_completion(pairs):
    if ask_router("C1",pairs)=="YES": return ("CONTINUE","An explicit requested deliverable is missing; produce it before ending the turn.")
    if ask_router("C2",pairs)=="YES": return ("CONTINUE","A completion claim lacks observable support; obtain or report the required supporting result.")
    if ask_router("C3",pairs)=="YES": return ("CONTINUE","A requested portion remains partial; continue execution on the remaining gap.")
    if ask_router("C4",pairs)=="YES": return ("COMPLETE",None)
    return ("CONTINUE","The proposed response does not itself provide the requested result; continue until the result is actually deliverable.")

def run_router()->dict[str,Any]:
    pairs=[]; stopping_fact=None
    q1=ask_router("Q1",pairs)
    if q1=="YES":
        if ask_router("Q1.1",pairs)=="YES":
            cause=ask_router("Q1.2",pairs)
            if cause=="NO": return {"cycle_id":uuid.uuid4().hex,"scope":"worker","pairs":pairs,"directive":"CONTINUE","instruction":"Inspect the failure cause from observable evidence before deciding whether execution can stop."}
            alt=run_alt(pairs)
            if alt: target,instruction=alt
            else: target,instruction=run_impasse(pairs)
            return {"cycle_id":uuid.uuid4().hex,"scope":"worker","pairs":pairs,"directive":target,**({"instruction":instruction} if instruction else {})}
        if ask_router("Q1.2",pairs)=="NO":
            target,instruction=("CONTINUE","Inspect the failed path and identify its actual cause before stopping.")
        else:
            alt=run_alt(pairs)
            target,instruction=alt if alt else ("CONTINUE","The failed path does not establish whole-task impossibility; continue using another available approach.")
        return {"cycle_id":uuid.uuid4().hex,"scope":"worker","pairs":pairs,"directive":target,"instruction":instruction}
    for qid in ["Q2","Q3","Q4","Q5","Q6","Q7","Q8","Q9","Q10","Q11","Q12","Q13","Q14","Q15"]:
        a=ask_router(qid,pairs)
        if a=="NO": continue
        if qid=="Q2":
            if ask_router("Q2.1",pairs)=="NO": return {"cycle_id":uuid.uuid4().hex,"scope":"worker","pairs":pairs,"directive":"CONTINUE","instruction":"Test the claimed limitation directly before stopping."}
            if ask_router("Q2.2",pairs)=="ONLY_THIS_PATH":
                alt=run_alt(pairs); target,instruction=alt if alt else ("CONTINUE","Only one path is blocked; continue via another available path.")
            else: target,instruction=run_impasse(pairs)
        elif qid=="Q3":
            if ask_router("Q3.1",pairs)=="NO": target,instruction=("CONTINUE","The stopping requirement is not grounded in the request or governing instructions; continue without it.")
            elif ask_router("Q3.2",pairs) in {"YES","UNKNOWN"}: target,instruction=("CONTINUE","Continue by satisfying or testing another legitimate way to satisfy the requirement.")
            else: target,instruction=run_impasse(pairs)
        elif qid=="Q4":
            q41=ask_router("Q4.1",pairs)
            if q41=="YES": target,instruction=("CONTINUE","Existing user authorization is sufficient; perform the already-authorized action.")
            elif ask_router("Q4.2",pairs)=="YES": target,instruction=("CONTINUE","Earlier authorization remains valid; continue without re-requesting it.")
            elif ask_router("Q4.3",pairs)=="YES" and ask_router("Q4.4",pairs)=="NO": target,instruction=("CONTINUE","Implementation changed but the authorized objective did not; continue under existing authorization.")
            else: target,instruction=("CONTINUE","Continue as far as current authorization permits; ask only if a genuinely new authorization boundary remains.")
        elif qid=="Q5":
            if ask_router("Q5.1",pairs)=="NO": target,instruction=("CONTINUE","No concrete unknown has been identified; continue execution.")
            elif ask_router("Q5.2",pairs)=="NO": target,instruction=("CONTINUE","The unknown does not materially affect the next useful action; continue.")
            elif ask_router("Q5.3",pairs)=="YES": target,instruction=("CONTINUE","Resolve the value from already supplied context and continue.")
            elif ask_router("Q5.4",pairs)=="YES": target,instruction=("CONTINUE","Retrieve or determine the missing value using an available source or tool.")
            elif ask_router("Q5.5",pairs)=="YES": target,instruction=("CONTINUE","Use a bounded non-destructive assumption and continue while making the assumption explicit where relevant.")
            else: target,instruction=run_impasse(pairs)
        elif qid=="Q6":
            if ask_router("Q6.1",pairs)=="NO": target,instruction=("CONTINUE","Perform the available action instead of merely describing it.")
            else: continue
        elif qid=="Q7":
            if ask_router("Q7.1",pairs)=="YES" and ask_router("Q7.2",pairs)=="NO": target,instruction=("CONTINUE","Obtain the substantive observable result before responding.")
            else: continue
        elif qid=="Q8": target,instruction=("CONTINUE","Perform the independent requested work that remains available.")
        elif qid=="Q9":
            if ask_router("Q9.1",pairs)=="YES": target,instruction=("CONTINUE","Use the latest applicable request/state and continue.")
            else: target,instruction=("CONTINUE","Reconcile the task with the latest applicable request before stopping.")
        elif qid=="Q10":
            if ask_router("Q10.1",pairs)=="NO": target,instruction=("CONTINUE","Discard the assistant-introduced blocker and continue toward the user's actual request.")
            elif ask_router("Q10.2",pairs)=="YES": target,instruction=("CONTINUE","Narrow the legitimate constraint to the scope actually required and continue.")
            else: continue
        elif qid=="Q11":
            if ask_router("Q11.1",pairs)=="YES": target,instruction=("CONTINUE","Use the directly suited available tool or source for the unmet requirement.")
            else: continue
        elif qid=="Q12":
            if ask_router("Q12.1",pairs)=="NO": target,instruction=("CONTINUE","Do not defer unfinished work to an uninvolved future mechanism; execute it now.")
            else: continue
        elif qid=="Q13":
            if ask_router("Q13.1",pairs)=="NO": target,instruction=("CONTINUE","Stop performing the unrequested execution and answer the actual non-execution request.")
            else: continue
        elif qid=="Q14":
            if ask_router("Q14.1",pairs)=="NO": target,instruction=("CONTINUE","Do not let the support process block substantive execution; continue the task.")
            elif ask_router("Q14.2",pairs)=="YES": target,instruction=("CONTINUE","Satisfy the required support process now and immediately continue substantive execution.")
            else: target,instruction=run_impasse(pairs)
        else: # Q15
            stopping_fact=ask_router("Q15.1",pairs)
            if stopping_fact=="NONE": target,instruction=("CONTINUE","No observable stopping fact exists; continue execution.")
            elif ask_router("Q15.2",pairs)=="NO": target,instruction=("CONTINUE","Verify the claimed stopping fact where testing is available.")
            elif ask_router("Q15.3",pairs) in {"YES","UNKNOWN"}: target,instruction=("CONTINUE","Change or test the execution path while preserving the requested result.")
            else: target,instruction=run_impasse(pairs)
        cycle={"cycle_id":uuid.uuid4().hex,"scope":"worker","pairs":pairs,"directive":target}
        if instruction: cycle["instruction"]=instruction
        if target=="IMPASSE": cycle["impasse_evidence"]=stopping_fact or "No additional impasse evidence was captured beyond the recorded router answers."
        return cycle
    target,instruction=run_completion(pairs)
    cycle={"cycle_id":uuid.uuid4().hex,"scope":"worker","pairs":pairs,"directive":target}
    if instruction: cycle["instruction"]=instruction
    return cycle

# --- prompt preprocessor --------------------------------------------------

PREPROCESSOR_GOVERNING_KINDS = {
    "CONSTRAINT":"Limits how one or more actions may be performed.",
    "PROHIBITION":"States something that must not occur or must not be included.",
    "PERMISSION":"States an action or method that the user explicitly permits.",
    "SOURCE_RESTRICTION":"Limits information acquisition to specified sources or source classes.",
    "TEMPORAL_RESTRICTION":"Limits execution or source selection by time or recency.",
    "LOCATION_RESTRICTION":"Limits execution or selection by place, environment, or storage location.",
    "FORMAT_REQUIREMENT":"Requires a particular representation or output format.",
    "QUALITY_REQUIREMENT":"Requires a stated quality, validation, or evidence threshold.",
    "ORDERING_REQUIREMENT":"Requires an explicit sequence among otherwise identified actions.",
}
PREPROCESSOR_MODIFIER_KINDS = {
    "QUANTITY":"Specifies how many or how much.",
    "SCOPE":"Limits or expands the set to which a requirement applies.",
    "CRITERION":"Provides a property used to compare, select, validate, classify, or score.",
    "ORDER":"Specifies required relative ordering.",
    "PRIORITY":"Specifies preference among actions or results.",
    "RECENCY":"Specifies temporal freshness such as latest or recent.",
    "COMPLETENESS":"Specifies all, every, complete, exhaustive, or analogous coverage.",
    "EXCLUSIVITY":"Specifies only, exactly, exclusively, or analogous exclusion of alternatives.",
}
PREPROCESSOR_DELIVERABLE_KINDS = {
    "ANSWER":"A user-facing answer or determination.",
    "ARTIFACT":"A newly produced file or other persistent object.",
    "MODIFICATION":"A requested change to existing state or an existing artifact.",
    "CALCULATION":"A computed user-facing value or result.",
    "COMPARISON":"A user-facing comparison of identified subjects.",
    "RECOMMENDATION":"A user-facing selection or recommendation.",
    "RETRIEVED_OBJECT":"A retrieved object or usable reference requested for delivery.",
    "REPORT":"A structured or narrative report of findings.",
    "CONFIRMATION":"A user-facing confirmation that an operation or state was established.",
}

def _enum_descriptions(mapping:dict[str,str])->str:
    return " | ".join(f"{key} — {description}" for key,description in mapping.items())

def _require_exact_keys(value:Any,expected:set[str],name:str)->dict[str,Any]:
    if not isinstance(value,dict) or set(value)!=expected: raise ValueError(f"{name} must contain exactly {sorted(expected)}")
    return value

def _string_array(value:Any,name:str,allow_empty:bool=True)->list[str]:
    if not isinstance(value,list) or (not allow_empty and not value): raise ValueError(f"{name} must be an array{' with at least one item' if not allow_empty else ''}")
    for item in value: require_text(item,name)
    return value

def _supporting_text(value:Any,name:str,original_prompt:str,allow_empty:bool=False)->list[str]:
    items=_string_array(value,name,allow_empty=allow_empty)
    for item in items:
        if item not in original_prompt: raise ValueError(f"{name} contains text not copied exactly from original_user_prompt")
    return items

def _numbered_objects(value:Any,prefix:str,name:str,keys:set[str],allow_empty:bool=True)->list[dict[str,Any]]:
    if not isinstance(value,list) or (not allow_empty and not value): raise ValueError(f"{name} must be an array{' with at least one item' if not allow_empty else ''}")
    for index,item in enumerate(value,1):
        _require_exact_keys(item,keys,f"{name}[{index}]")
        if item["id"]!=f"{prefix}{index}": raise ValueError(f"{name} IDs must be {prefix}1, {prefix}2, ... in order")
    return value

def _semantic_question(question_id:str,semantic_function:str,instruction:str,inputs:dict[str,Any],response_schema:dict[str,Any],constraints:list[str],validator)->Any:
    prompt={"protocol":PREPROCESSOR_PROTOCOL,"question_id":question_id,"semantic_function":semantic_function,"instruction":instruction,"inputs":inputs,"response_schema":response_schema,"constraints":constraints}
    while True:
        print(json.dumps(prompt,ensure_ascii=False),flush=True)
        line=sys.stdin.readline()
        if line=="": raise EOFError(f"EOF waiting for {question_id}")
        try: value=json.loads(line)
        except json.JSONDecodeError as exc:
            prompt={**prompt,"validation_error":f"Response must be one JSON value: {exc}"}; continue
        try:
            validator(value)
            return value
        except Exception as exc:
            prompt={**prompt,"validation_error":str(exc)}

def _validate_graph(actions:list[dict[str,Any]],dependencies:list[dict[str,Any]])->list[str]:
    ids=[item["id"] for item in actions]; valid=set(ids)
    incoming={item:0 for item in ids}; outgoing={item:[] for item in ids}
    for dep in dependencies:
        if dep["from_action"] not in valid or dep["to_action"] not in valid: raise ValueError("dependency references unknown action")
        if dep["from_action"]==dep["to_action"]: raise ValueError("action cannot depend on itself")
        outgoing[dep["from_action"]].append(dep["to_action"]); incoming[dep["to_action"]]+=1
    queue=[item for item in ids if incoming[item]==0]; out=[]
    while queue:
        current=queue.pop(0); out.append(current)
        for nxt in outgoing[current]:
            incoming[nxt]-=1
            if incoming[nxt]==0: queue.append(nxt)
    if len(out)!=len(actions): raise ValueError("preprocessor dependency graph contains a cycle")
    return out

def _pp1(original_prompt:str):
    def validate(v):
        _require_exact_keys(v,{"goal","supporting_text"},"PP1")
        require_text(v["goal"],"PP1.goal"); _supporting_text(v["supporting_text"],"PP1.supporting_text",original_prompt)
    return _semantic_question("PP1","IDENTIFY_GOAL","Read original_user_prompt. State the terminal result or state the user wants to exist when the request is fully satisfied. Do not describe implementation steps. Do not add requirements, assumptions, criteria, or constraints. supporting_text must contain one or more exact substrings copied from original_user_prompt that support the goal.",{"original_user_prompt":original_prompt},{"goal":"string","supporting_text":["exact substring from original_user_prompt"]},["Perform only semantic analysis; do not execute the user task.","Do not improve or broaden the request."],validate)

def _pp2(original_prompt:str,goal:dict[str,Any]):
    def validate(v):
        _require_exact_keys(v,{"requirements"},"PP2")
        for item in _numbered_objects(v["requirements"],"R","PP2.requirements",{"id","text","supporting_text"},allow_empty=False):
            require_text(item["text"],"PP2 requirement text"); _supporting_text(item["supporting_text"],"PP2 supporting_text",original_prompt)
    return _semantic_question("PP2","DECOMPOSE_REQUIREMENTS","Decompose original_user_prompt into every independently testable user requirement. Preserve semantic strength, quantities, restrictions, requested outputs, and qualifications. Do not combine requirements that could independently be satisfied or fail. supporting_text for each requirement must contain exact substrings copied from original_user_prompt.",{"original_user_prompt":original_prompt,"goal":goal},{"requirements":[{"id":"R#","text":"string","supporting_text":["exact substring"]}]},["Do not invent requirements.","Do not perform any requested action."],validate)

def _pp3(requirements:list[dict[str,Any]]):
    req_ids={x["id"] for x in requirements}
    def validate(v):
        _require_exact_keys(v,{"actions"},"PP3")
        for item in _numbered_objects(v["actions"],"A","PP3.actions",{"id","type","subtype","semantic_description","requirement_ids"},allow_empty=False):
            if item["type"] not in ACTION_SUBTYPES or item["subtype"] not in ACTION_SUBTYPES[item["type"]]: raise ValueError("PP3 action ontology invalid")
            require_text(item["semantic_description"],"PP3 semantic_description")
            refs=_string_array(item["requirement_ids"],"PP3 requirement_ids",allow_empty=False)
            if any(x not in req_ids for x in refs): raise ValueError("PP3 references unknown requirement")
    return _semantic_question("PP3","DECOMPOSE_ACTIONS",f"Identify the smallest meaningful material operations required to satisfy the listed requirements. Do not perform any operation. Classify every operation using exactly one supplied action type and subtype. Use these self-describing choices: {ACTION_ONTOLOGY_TEXT}",{"requirements":requirements,"action_ontology":ACTION_ONTOLOGY_DESCRIPTIONS},{"actions":[{"id":"A#","type":"ACTION_TYPE","subtype":"ACTION_SUBTYPE","semantic_description":"string","requirement_ids":["R#"]}]},["Every action must support at least one requirement.","Do not add actions that merely improve the task beyond the user's request."],validate)

def _pp4(original_prompt:str,requirements:list[dict[str,Any]],actions:list[dict[str,Any]]):
    action_ids={x["id"] for x in actions}
    def validate(v):
        _require_exact_keys(v,{"action_arguments"},"PP4")
        items=v["action_arguments"]
        if not isinstance(items,list) or len(items)!=len(actions): raise ValueError("PP4 must contain exactly one argument object per action")
        seen=set()
        for item in items:
            _require_exact_keys(item,{"action_id","target","inputs","outputs","referents"},"PP4 action argument")
            if item["action_id"] not in action_ids or item["action_id"] in seen: raise ValueError("PP4 action_id invalid or duplicate")
            seen.add(item["action_id"]); require_text(item["target"],"PP4 target")
            _string_array(item["inputs"],"PP4 inputs"); _string_array(item["outputs"],"PP4 outputs"); _string_array(item["referents"],"PP4 referents")
    return _semantic_question("PP4","IDENTIFY_ACTION_ARGUMENTS","For each action, identify what it acts on, what semantic inputs it requires, what result it produces, and the relevant referents. Do not invent inputs not supported by the request or necessary outputs of another identified action.",{"original_user_prompt":original_prompt,"requirements":requirements,"actions":actions},{"action_arguments":[{"action_id":"A#","target":"string","inputs":["string"],"outputs":["string"],"referents":["string"]}]},["Return exactly one object per action.","Do not perform the actions."],validate)

def _pp5(original_prompt:str,actions:list[dict[str,Any]]):
    action_ids={x["id"] for x in actions}; kinds=set(PREPROCESSOR_GOVERNING_KINDS)
    def validate(v):
        _require_exact_keys(v,{"governing_fragments"},"PP5")
        for item in _numbered_objects(v["governing_fragments"],"G","PP5.governing_fragments",{"id","kind","text","applies_to","supporting_text"},allow_empty=True):
            if item["kind"] not in kinds: raise ValueError("PP5 governing kind invalid")
            require_text(item["text"],"PP5 text"); refs=_string_array(item["applies_to"],"PP5 applies_to",allow_empty=False)
            if any(x not in action_ids for x in refs): raise ValueError("PP5 unknown action")
            _supporting_text(item["supporting_text"],"PP5 supporting_text",original_prompt)
    return _semantic_question("PP5","IDENTIFY_GOVERNING_FRAGMENTS",f"Identify semantic elements in the user request that govern how one or more actions may be performed but are not themselves actions. Use only these kinds: {_enum_descriptions(PREPROCESSOR_GOVERNING_KINDS)} Preserve original semantic strength and scope.",{"original_user_prompt":original_prompt,"actions":actions},{"governing_fragments":[{"id":"G#","kind":"KIND","text":"string","applies_to":["A#"],"supporting_text":["exact substring"]}]},["Return [] when no governing fragment is present.","Do not invent prudent or useful constraints."],validate)

def _pp6(original_prompt:str,requirements:list[dict[str,Any]],actions:list[dict[str,Any]]):
    valid={x["id"] for x in requirements}|{x["id"] for x in actions}; kinds=set(PREPROCESSOR_MODIFIER_KINDS)
    def validate(v):
        _require_exact_keys(v,{"modifiers"},"PP6")
        for item in _numbered_objects(v["modifiers"],"M","PP6.modifiers",{"id","kind","value","applies_to","supporting_text"},allow_empty=True):
            if item["kind"] not in kinds: raise ValueError("PP6 modifier kind invalid")
            require_text(str(item["value"]),"PP6 value"); refs=_string_array(item["applies_to"],"PP6 applies_to",allow_empty=False)
            if any(x not in valid for x in refs): raise ValueError("PP6 unknown reference")
            _supporting_text(item["supporting_text"],"PP6 supporting_text",original_prompt)
    return _semantic_question("PP6","IDENTIFY_MODIFIERS",f"Identify every quantity, scope operator, selection/comparison criterion, recency requirement, exclusivity operator, completeness requirement, priority, or other represented modifier. Use only these kinds: {_enum_descriptions(PREPROCESSOR_MODIFIER_KINDS)}",{"original_user_prompt":original_prompt,"requirements":requirements,"actions":actions},{"modifiers":[{"id":"M#","kind":"KIND","value":"string","applies_to":["R# or A#"],"supporting_text":["exact substring"]}]},["Pay particular attention to words such as only, all, every, latest, recent, exactly, at least, at most, before, and after.","Do not create implied preferences."],validate)

def _pp7(actions:list[dict[str,Any]],arguments:list[dict[str,Any]],governing:list[dict[str,Any]]):
    action_ids={x["id"] for x in actions}
    def validate(v):
        _require_exact_keys(v,{"dependencies"},"PP7")
        if not isinstance(v["dependencies"],list): raise ValueError("PP7 dependencies must be array")
        for dep in v["dependencies"]:
            _require_exact_keys(dep,{"from_action","to_action","relationship"},"PP7 dependency")
            if dep["from_action"] not in action_ids or dep["to_action"] not in action_ids: raise ValueError("PP7 unknown action")
            if dep["relationship"] not in {"REQUIRES_OUTPUT","REQUIRES_COMPLETION"}: raise ValueError("PP7 relationship invalid")
        _validate_graph(actions,v["dependencies"])
    return _semantic_question("PP7","IDENTIFY_DEPENDENCIES","Determine which actions semantically require outputs or completion of other actions before they can be performed. Do not impose an order merely because actions were mentioned in that order. Use REQUIRES_OUTPUT — the earlier action produces an input required by the later action; REQUIRES_COMPLETION — the earlier action must complete first even when no direct output is consumed.",{"actions":actions,"action_arguments":arguments,"governing_fragments":governing},{"dependencies":[{"from_action":"A#","to_action":"A#","relationship":"REQUIRES_OUTPUT | REQUIRES_COMPLETION"}]},["Return [] when actions are semantically independent.","The graph must be acyclic."],validate)

def _pp8(original_prompt:str,actions:list[dict[str,Any]]):
    action_ids={x["id"] for x in actions}
    def arr(value,name,prefix,keys):
        for item in _numbered_objects(value,prefix,name,keys,allow_empty=True):
            refs=_string_array(item["applies_to"],f"{name} applies_to",allow_empty=False)
            if any(x not in action_ids for x in refs): raise ValueError(f"{name} unknown action")
            _supporting_text(item["supporting_text"],f"{name} supporting_text",original_prompt)
            require_text(item["text"],f"{name} text")
    def validate(v):
        _require_exact_keys(v,{"conditions","alternatives","fallbacks"},"PP8")
        arr(v["conditions"],"PP8.conditions","C",{"id","text","applies_to","supporting_text"})
        arr(v["alternatives"],"PP8.alternatives","L",{"id","text","applies_to","supporting_text"})
        arr(v["fallbacks"],"PP8.fallbacks","F",{"id","text","applies_to","supporting_text"})
    return _semantic_question("PP8","IDENTIFY_BRANCHING","Identify explicit or necessarily represented conditional execution, alternatives, fallbacks, exceptions, and mutually exclusive paths. Do not create fallback behavior merely because one might be useful.",{"original_user_prompt":original_prompt,"actions":actions},{"conditions":[{"id":"C#","text":"string","applies_to":["A#"],"supporting_text":["exact substring"]}],"alternatives":[{"id":"L#","text":"string","applies_to":["A#"],"supporting_text":["exact substring"]}],"fallbacks":[{"id":"F#","text":"string","applies_to":["A#"],"supporting_text":["exact substring"]}]},["Return empty arrays for absent categories.","Do not execute a branch."],validate)

def _pp9(original_prompt:str,goal:dict[str,Any],requirements:list[dict[str,Any]]):
    req_ids={x["id"] for x in requirements}; kinds=set(PREPROCESSOR_DELIVERABLE_KINDS)
    def validate(v):
        _require_exact_keys(v,{"deliverables"},"PP9")
        for item in _numbered_objects(v["deliverables"],"D","PP9.deliverables",{"id","kind","description","requirement_ids","supporting_text"},allow_empty=False):
            if item["kind"] not in kinds: raise ValueError("PP9 kind invalid")
            require_text(item["description"],"PP9 description"); refs=_string_array(item["requirement_ids"],"PP9 requirement_ids",allow_empty=False)
            if any(x not in req_ids for x in refs): raise ValueError("PP9 unknown requirement")
            _supporting_text(item["supporting_text"],"PP9 supporting_text",original_prompt)
    return _semantic_question("PP9","IDENTIFY_DELIVERABLES",f"Identify everything the user expects to receive, observe, or have changed when the task is complete. Distinguish intermediate action outputs from user-facing deliverables. Use only these kinds: {_enum_descriptions(PREPROCESSOR_DELIVERABLE_KINDS)}",{"original_user_prompt":original_prompt,"goal":goal,"requirements":requirements},{"deliverables":[{"id":"D#","kind":"KIND","description":"string","requirement_ids":["R#"],"supporting_text":["exact substring"]}]},["Every deliverable must map to at least one requirement.","Do not add presentation requirements the user did not request."],validate)

def _pp10(original_prompt:str,current_ir:dict[str,Any]):
    def validate(v):
        _require_exact_keys(v,{"ambiguities"},"PP10")
        items=_numbered_objects(v["ambiguities"],"U","PP10.ambiguities",{"id","subject","interpretations","material","supporting_text"},allow_empty=True)
        for item in items:
            require_text(item["subject"],"PP10 subject"); interpretations=_string_array(item["interpretations"],"PP10 interpretations",allow_empty=False)
            if len(interpretations)<2: raise ValueError("PP10 ambiguity needs at least two interpretations")
            if not isinstance(item["material"],bool): raise ValueError("PP10 material must be boolean")
            _supporting_text(item["supporting_text"],"PP10 supporting_text",original_prompt)
    return _semantic_question("PP10","DETECT_AMBIGUITY","Identify terms, referents, scopes, criteria, quantities, relationships, or requested outcomes that have more than one materially different plausible interpretation. Do not resolve an ambiguity. Report the plausible interpretations and whether the difference would materially change execution or correctness.",{"original_user_prompt":original_prompt,"current_semantic_representation":current_ir},{"ambiguities":[{"id":"U#","subject":"string","interpretations":["string","string"],"material":"boolean","supporting_text":["exact substring"]}]},["Do not invent ambiguity merely because more detail could be supplied.","Do not resolve an identified ambiguity."],validate)

def _render_fragment(qid:str,semantic_function:str,instruction:str,inputs:dict[str,Any])->str:
    def validate(v): _require_exact_keys(v,{"fragment"},qid); require_text(v["fragment"],f"{qid}.fragment")
    return _semantic_question(qid,semantic_function,instruction,inputs,{"fragment":"string"},["Generate only the requested fragment.","Do not add semantic content not represented in inputs."],validate)["fragment"]

def _render_fragments(ir:dict[str,Any])->dict[str,Any]:
    fragments={"goal":"","actions":{},"governing":{},"conditions":{},"alternatives":{},"fallbacks":{},"deliverables":{}}
    fragments["goal"]=_render_fragment("PP11-GOAL","RENDER_GOAL_FRAGMENT","Express the supplied goal as one concise task-goal clause. Preserve its semantic strength and referents exactly. Do not add implementation steps.",{"goal":ir["goal"]})
    args_by={x["action_id"]:x for x in ir["action_arguments"]}
    for action in ir["actions"]:
        aid=action["id"]; modifiers=[x for x in ir["modifiers"] if aid in x["applies_to"]]
        fragments["actions"][aid]=_render_fragment(f"PP11-{aid}","RENDER_ACTION_FRAGMENT","Express the supplied action as one executable imperative clause. Preserve exactly the action semantics, target, inputs, outputs, referents, and modifiers. Do not merge it with another action and do not add planning or rationale.",{"action":action,"arguments":args_by[aid],"modifiers":modifiers})
    for item in ir["governing_fragments"]:
        fragments["governing"][item["id"]]=_render_fragment(f"PP11-{item['id']}","RENDER_GOVERNING_FRAGMENT","Express this governing semantic element as one concise instruction clause. Preserve its strength and scope exactly.",{"governing_fragment":item})
    for item in ir["conditions"]:
        fragments["conditions"][item["id"]]=_render_fragment(f"PP11-{item['id']}","RENDER_CONDITION_FRAGMENT","Express this condition as one concise conditional instruction clause without adding consequences not represented by applies_to.",{"condition":item})
    for item in ir["alternatives"]:
        fragments["alternatives"][item["id"]]=_render_fragment(f"PP11-{item['id']}","RENDER_ALTERNATIVE_FRAGMENT","Express this alternative-path relationship as one concise instruction clause. Preserve whether the represented paths are mutually exclusive or optional.",{"alternative":item})
    for item in ir["fallbacks"]:
        fragments["fallbacks"][item["id"]]=_render_fragment(f"PP11-{item['id']}","RENDER_FALLBACK_FRAGMENT","Express this explicit fallback relationship as one concise instruction clause without inventing triggering conditions.",{"fallback":item})
    for item in ir["deliverables"]:
        fragments["deliverables"][item["id"]]=_render_fragment(f"PP11-{item['id']}","RENDER_DELIVERABLE_FRAGMENT","Express this required user-facing deliverable as one concise imperative clause without adding content requirements.",{"deliverable":item})
    return fragments

def _recompose(ir:dict[str,Any],fragments:dict[str,Any])->tuple[str,str]:
    order=_validate_graph(ir["actions"],ir["dependencies"])
    sections=["TASK\n"+fragments["goal"]]
    if order:
        sections.append("PERFORM\n"+"\n".join(f"{i}. {fragments['actions'][aid]}" for i,aid in enumerate(order,1)))
    if fragments["governing"]:
        sections.append("CONSTRAINTS\n"+"\n".join(f"- {fragments['governing'][item['id']]}" for item in ir["governing_fragments"]))
    branch_lines=[]
    for group,key in [("conditions","conditions"),("alternatives","alternatives"),("fallbacks","fallbacks")]:
        branch_lines.extend(f"- {fragments[group][item['id']]}" for item in ir[key])
    if branch_lines: sections.append("CONDITIONS AND ALTERNATIVES\n"+"\n".join(branch_lines))
    sections.append("DELIVER\n"+"\n".join(f"- {fragments['deliverables'][item['id']]}" for item in ir["deliverables"]))
    task_prompt="\n\n".join(sections)
    first_command=fragments["actions"][order[0]] if order else "Perform exactly one material next action toward task_prompt."
    return task_prompt,first_command

def _pp12(original_prompt:str,ir:dict[str,Any],candidate_task_prompt:str):
    keys={"omitted","added","strength_changed","referent_changed","other_semantic_changes"}
    def validate(v):
        _require_exact_keys(v,keys,"PP12")
        for key in keys: _string_array(v[key],f"PP12.{key}")
    return _semantic_question("PP12","AUDIT_RECOMPOSITION","Compare original_user_prompt, prompt_ir, and candidate_task_prompt. Do not improve or rewrite either prompt. Report only semantic information that was omitted, added, strengthened, weakened, assigned to the wrong referent, or otherwise changed. Use empty arrays when no issue of a category exists.",{"original_user_prompt":original_prompt,"prompt_ir":ir,"candidate_task_prompt":candidate_task_prompt},{"omitted":["string"],"added":["string"],"strength_changed":["string"],"referent_changed":["string"],"other_semantic_changes":["string"]},["This is an equivalence audit, not an optimization task.","Do not propose improvements."],validate)

def run_prompt_preprocessor(original_prompt:str)->dict[str,Any]:
    goal=_pp1(original_prompt)
    requirements=_pp2(original_prompt,goal)["requirements"]
    actions=_pp3(requirements)["actions"]
    arguments=_pp4(original_prompt,requirements,actions)["action_arguments"]
    governing=_pp5(original_prompt,actions)["governing_fragments"]
    modifiers=_pp6(original_prompt,requirements,actions)["modifiers"]
    dependencies=_pp7(actions,arguments,governing)["dependencies"]
    branching=_pp8(original_prompt,actions)
    deliverables=_pp9(original_prompt,goal,requirements)["deliverables"]
    partial_ir={"schema":"prompt-ir-v1","goal":goal,"requirements":requirements,"actions":actions,"action_arguments":arguments,"governing_fragments":governing,"modifiers":modifiers,"dependencies":dependencies,"conditions":branching["conditions"],"alternatives":branching["alternatives"],"fallbacks":branching["fallbacks"],"deliverables":deliverables}
    ambiguities=_pp10(original_prompt,partial_ir)["ambiguities"]
    ir={**partial_ir,"ambiguities":ambiguities}
    if any(item["material"] for item in ambiguities):
        return {"status":"FALLBACK","reason":"MATERIAL_AMBIGUITY","task_prompt":original_prompt,"prompt_ir":ir}
    fragments=_render_fragments(ir)
    candidate,first_command=_recompose(ir,fragments)
    audit=_pp12(original_prompt,ir,candidate)
    if any(audit[key] for key in audit):
        return {"status":"FALLBACK","reason":"SEMANTIC_AUDIT_FAILED","task_prompt":original_prompt,"prompt_ir":ir,"fragments":fragments,"audit":audit}
    return {"status":"ACCEPTED","reason":None,"task_prompt":candidate,"first_command":first_command,"prompt_ir":ir,"fragments":fragments,"audit":audit}

# --- payload/state --------------------------------------------------------

def seal_payload(payload:dict[str,Any])->dict[str,Any]:
    base={k:v for k,v in payload.items() if k!="payload_sha256"}; payload["payload_sha256"]=sha256_json(base); return payload

def verify_payload(payload:dict[str,Any])->dict[str,Any]:
    if not isinstance(payload,dict) or payload.get("schema")!=PAYLOAD_SCHEMA: raise ValueError("invalid payload schema")
    expected=payload.get("payload_sha256"); base={k:v for k,v in payload.items() if k!="payload_sha256"}
    if not isinstance(expected,str) or sha256_json(base)!=expected: raise ValueError("payload integrity failure")
    if payload.get("authority") not in {"TASK_ACTION","FINAL_RESPONSE"}: raise ValueError("invalid authority")
    if not isinstance(payload.get("state"),dict): raise ValueError("state missing")
    if payload["authority"]=="TASK_ACTION":
        require_text(payload.get("task_prompt"),"task_prompt"); require_text(payload.get("command"),"command")
    return payload

def new_state(user_prompt:str)->dict[str,Any]:
    if not isinstance(user_prompt,str) or not user_prompt:
        raise ValueError("initialization user_prompt must be a non-empty string")
    record_state=record_latest(runtime_record_dir())
    return {
        "control_version":CONTROL_VERSION,
        "sequence":1,
        "record_state":record_state,
        "turn_start_action_count":record_state["action_count"],
        "last_router":None,
        "original_user_prompt":user_prompt,
        "task_prompt":user_prompt,
        "prompt_intake_mode":"VERBATIM",
        "preprocessor_requested":False,
        "preprocessor_status":"NOT_REQUESTED",
    }

def issue_task_payload(state:dict[str,Any],command:str,context:dict[str,Any]|None=None)->dict[str,Any]:
    task_prompt=require_text(state.get("task_prompt"),"state.task_prompt")
    return seal_payload({"schema":PAYLOAD_SCHEMA,"authority":"TASK_ACTION","task_prompt":task_prompt,"command":command,"context":context or {},"behavioral_instructions":BEHAVIORAL_INSTRUCTIONS,"state":state})

def issue_final_payload(state:dict[str,Any],router_cycle:dict[str,Any])->dict[str,Any]:
    rs=state["record_state"]
    record_content=None
    if rs.get("record") and Path(rs["record"]).exists():
        record_content=record_read(Path(rs["record"]))
    task_prompt=require_text(state.get("task_prompt"),"state.task_prompt")
    return seal_payload({"schema":PAYLOAD_SCHEMA,"authority":"FINAL_RESPONSE","task_prompt":task_prompt,"command":"Construct and deliver the final user-facing response satisfying task_prompt from the current conversation and terminal context. Do not perform additional substantive task work.","context":{"terminal_directive":router_cycle["directive"],"router_cycle":router_cycle,"execution_record_path":rs.get("record"),"execution_record_filename":rs.get("record_name"),"execution_record":record_content,"current_turn_action_range":{"start_sequence":state["turn_start_action_count"]+1,"end_sequence":rs["action_count"]}},"behavioral_instructions":BEHAVIORAL_INSTRUCTIONS,"state":state})

def process_returned_payload(payload:dict[str,Any])->dict[str,Any]:
    payload=verify_payload(payload)
    if payload.get("authority")!="TASK_ACTION":
        raise ValueError("only TASK_ACTION payloads may be returned to the bundle")
    state=payload["state"]
    rs=state["record_state"]
    record_append(rs,{"action_type":"recorder_invocation","scope":"worker"})
    questionnaire=run_action_questionnaire()
    record_append(rs,questionnaire["action"])
    end_attempt=questionnaire["state"]["answers"]["AQ1"]=="YES"
    state["sequence"]+=1
    if not end_attempt:
        return issue_task_payload(state,"Perform exactly one next material action toward task_prompt. Return this complete payload unchanged when that action reaches a stop point.",{"questionnaire":"nonterminal"})
    router_cycle=run_router()
    record_append(rs,{"action_type":"end_turn_result","scope":"worker","router_cycle":router_cycle})
    state["last_router"]=router_cycle
    if router_cycle["directive"]=="CONTINUE":
        return issue_task_payload(state,router_cycle.get("instruction") or "Continue execution toward task_prompt.",{"router_cycle":router_cycle})
    return issue_final_payload(state,router_cycle)

def emit(payload:dict[str,Any])->int:
    print(json.dumps(payload,ensure_ascii=False),flush=True)
    return 0

def parse_initialization(value:Any)->tuple[str,bool]:
    if not isinstance(value,dict): raise ValueError("initialization must be an object")
    required={"schema","type","user_prompt"}; allowed=required|{"preprocessor"}
    if not required.issubset(value) or not set(value).issubset(allowed):
        raise ValueError("initialization object must contain schema, type, and user_prompt, with only optional preprocessor")
    if value.get("schema")!=INITIALIZATION_SCHEMA:
        raise ValueError("initialization schema is invalid")
    if value.get("type")!="INITIALIZE":
        raise ValueError("initialization type must be INITIALIZE")
    requested="preprocessor" in value
    if requested and value.get("preprocessor") is not True:
        raise ValueError("when present, initialization.preprocessor must be JSON true")
    return require_text(value.get("user_prompt"),"initialization.user_prompt"),requested

def process_initialization(value:Any)->dict[str,Any]:
    user_prompt,preprocessor_requested=parse_initialization(value)
    state=new_state(user_prompt)
    state["preprocessor_requested"]=preprocessor_requested
    command="Execute exactly one material next action toward task_prompt. Return this complete payload unchanged when that action completes, fails, or reaches an attempted end-of-turn stop point."
    context={"initialization":"accepted","preprocessor_requested":preprocessor_requested}
    if preprocessor_requested:
        try:
            result=run_prompt_preprocessor(user_prompt)
            state["task_prompt"]=result["task_prompt"]
            state["preprocessor_status"]=result["status"]
            state["preprocessor_reason"]=result.get("reason")
            state["prompt_intake_mode"]="SEMANTIC_RECOMPOSITION" if result["status"]=="ACCEPTED" else "VERBATIM_FALLBACK"
            state["prompt_ir"]=result.get("prompt_ir")
            if result["status"]=="ACCEPTED":
                state["preprocessor_fragments"]=result.get("fragments")
                state["preprocessor_audit"]=result.get("audit")
                command=result["first_command"]
            context.update({"preprocessor_status":state["preprocessor_status"],"preprocessor_reason":state.get("preprocessor_reason")})
        except Exception as exc:
            state["task_prompt"]=user_prompt
            state["prompt_intake_mode"]="VERBATIM_FALLBACK"
            state["preprocessor_status"]="FALLBACK"
            state["preprocessor_reason"]="PROTOCOL_ERROR"
            state["preprocessor_error"]={"type":type(exc).__name__,"detail":str(exc)}
            context.update({"preprocessor_status":"FALLBACK","preprocessor_reason":"PROTOCOL_ERROR"})
    else:
        context["preprocessor_status"]="NOT_REQUESTED"
    return issue_task_payload(state,command,context)

def main()->int:
    first=sys.stdin.readline()
    if first=="" or not first.strip():
        print(json.dumps({"schema":PAYLOAD_SCHEMA,"authority":"NONE","execution_authority":False,"error":"InitializationRequired","detail":f"Invoke with one JSON line using schema {INITIALIZATION_SCHEMA} and type INITIALIZE, or return a previously issued payload."},ensure_ascii=False),flush=True)
        return 2
    try:
        value=json.loads(first)
        if isinstance(value,dict) and value.get("schema")==INITIALIZATION_SCHEMA:
            return emit(process_initialization(value))
        return emit(process_returned_payload(value))
    except Exception as exc:
        print(json.dumps({"schema":PAYLOAD_SCHEMA,"authority":"NONE","execution_authority":False,"error":type(exc).__name__,"detail":str(exc)},ensure_ascii=False),flush=True)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
