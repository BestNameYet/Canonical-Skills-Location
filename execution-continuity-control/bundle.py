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
"Q12.1:YES":"Report only what the real invoked future mechanism establishes and perform all other work possible now.",
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

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00","Z")

def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")

def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",",":"))

def payload_digest(payload: dict[str, Any]) -> str:
    clone = dict(payload)
    clone.pop("payload_sha256", None)
    return hashlib.sha256(canonical_json(clone).encode()).hexdigest()

def seal_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload["payload_sha256"] = payload_digest(payload)
    return payload

def verify_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    if payload.get("schema") != PAYLOAD_SCHEMA:
        raise ValueError("payload schema is invalid")
    supplied = payload.get("payload_sha256")
    if not isinstance(supplied, str) or supplied != payload_digest(payload):
        raise ValueError("payload was changed after issue")
    state = payload.get("state")
    if not isinstance(state, dict) or state.get("control_version") != CONTROL_VERSION:
        raise ValueError("payload state is invalid")
    return payload

def runtime_record_dir() -> Path:
    base = Path("/mnt/data")
    if base.exists() and os.access(base, os.W_OK):
        return base
    return Path.cwd()

def record_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def record_read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def record_write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)

def record_stamp(filename: str) -> str:
    match = STAMP_RE.fullmatch(filename)
    if not match:
        raise ValueError("record filename is invalid")
    return match.group(1)

def record_latest(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates=[]
    for path in output_dir.glob(f"{RECORD_PREFIX}*{RECORD_SUFFIX}"):
        match=STAMP_RE.fullmatch(path.name)
        if match:
            candidates.append((match.group(1),path))
    if not candidates:
        return {"output_dir":str(output_dir),"record":None,"record_name":None,"record_id":uuid.uuid4().hex,"action_count":0}
    _,path=max(candidates,key=lambda x:x[0])
    record=record_read(path)
    return {"output_dir":str(output_dir),"record":str(path),"record_name":path.name,"record_id":record["record_id"],"action_count":len(record["actions"])}

def record_append(record_state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    output_dir=Path(record_state["output_dir"])
    prior=None
    prior_hash=None
    prior_name=record_state.get("record_name")
    if record_state.get("record"):
        prior_path=Path(record_state["record"])
        prior=record_read(prior_path)
        if prior["record_id"] != record_state["record_id"]:
            raise ValueError("record_id mismatch")
        prior_hash=record_sha256(prior_path)
    actions=[] if prior is None else [dict(x) for x in prior["actions"]]
    action={**payload,"sequence":len(actions)+1,"recorded_at":now_iso()}
    actions.append(action)
    stamp=now_stamp()
    if prior_name:
        prior_stamp=record_stamp(prior_name)
        if stamp <= prior_stamp:
            dt=datetime.strptime(prior_stamp,"%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc)+timedelta(microseconds=1)
            stamp=dt.strftime("%Y%m%dT%H%M%S%fZ")
    filename=f"{RECORD_PREFIX}{stamp}{RECORD_SUFFIX}"
    record={"record_id":record_state["record_id"],"snapshot_created_at":now_iso(),"predecessor":None if prior is None else {"filename":prior_name,"sha256":prior_hash},"actions":actions}
    path=output_dir/filename
    record_write(path,record)
    record_state.update({"record":str(path),"record_name":filename,"action_count":len(actions)})
    return {"record":str(path),"record_filename":filename,"record_sha256":record_sha256(path),"record_id":record_state["record_id"],"sequence":len(actions)}

def normalize_yes_no(raw: str, qid: str) -> str:
    value={"Y":"YES","N":"NO"}.get(raw.strip().upper(),raw.strip().upper())
    if value not in {"YES","NO"}:
        raise ValueError(f"{qid} requires YES or NO")
    return value

def parse_json_answer(raw: str, qid: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{qid} requires valid JSON") from exc

def require_text(value: Any, label: str, allow_empty: bool=False) -> str:
    if not isinstance(value,str) or (not allow_empty and not value.strip()):
        raise ValueError(f"{label} must be {'a string' if allow_empty else 'a non-empty string'}")
    return value

def numbered(value: Any,prefix:str,label:str,require_nonempty:bool=True) -> list[dict[str,Any]]:
    if not isinstance(value,list) or (require_nonempty and not value):
        raise ValueError(f"{label} must be an array")
    for i,item in enumerate(value,1):
        if not isinstance(item,dict) or set(item)!={"id","text"} or item.get("id")!=f"{prefix}{i}":
            raise ValueError(f"{label} numbering/shape is invalid")
        require_text(item["text"],f"{label}.text")
    return value

def answer_ids(state:dict[str,Any],prefix:str)->set[str]:
    key={"UI":"AQ3","A":"AQ4","P":"AQ6","E":"AQ8"}[prefix]
    return {x["id"] for x in state["answers"].get(key,[])}

def validate_action_answer(qid:str,raw:str,state:dict[str,Any])->Any:
    if qid in {"AQ1","AQ5"}:
        return normalize_yes_no(raw,qid)
    if qid=="AQ2":
        return require_text(raw.strip(),qid)
    if qid=="AQ3":
        return numbered(parse_json_answer(raw,qid),"UI",qid)
    if qid=="AQ4":
        value=parse_json_answer(raw,qid)
        if not isinstance(value,list) or not value: raise ValueError("AQ4 must be a non-empty array")
        for i,item in enumerate(value,1):
            if not isinstance(item,dict) or set(item)!={"id","type","subtype","target"} or item.get("id")!=f"A{i}": raise ValueError("AQ4 shape is invalid")
            if item["type"] not in ACTION_SUBTYPES or item["subtype"] not in ACTION_SUBTYPES[item["type"]]: raise ValueError("AQ4 action type/subtype is invalid")
            require_text(item["target"],"AQ4.target")
        return value
    if qid=="AQ6":
        value=parse_json_answer(raw,qid); has_plan=state["answers"].get("AQ5")=="YES"
        value=numbered(value,"P",qid,has_plan)
        if not has_plan and value: raise ValueError("AQ6 must be [] when AQ5 is NO")
        return value
    if qid=="AQ7":
        value=parse_json_answer(raw,qid); aids=answer_ids(state,"A"); uids=answer_ids(state,"UI")
        if not isinstance(value,list) or len(value)!=len(aids): raise ValueError("AQ7 must map every action")
        seen=set()
        for item in value:
            if not isinstance(item,dict) or set(item)!={"action_id","intent_ids","relation"}: raise ValueError("AQ7 shape is invalid")
            if item["action_id"] not in aids or item["action_id"] in seen or item["relation"] not in INTENT_RELATIONS: raise ValueError("AQ7 references are invalid")
            ids=item["intent_ids"]
            if not isinstance(ids,list) or len(ids)!=len(set(ids)) or any(x not in uids for x in ids): raise ValueError("AQ7 intent_ids invalid")
            if (item["relation"]=="NONE") != (not ids): raise ValueError("AQ7 NONE relation mismatch")
            seen.add(item["action_id"])
        return value
    if qid=="AQ8":
        value=parse_json_answer(raw,qid)
        if not isinstance(value,list): raise ValueError("AQ8 must be an array")
        for i,item in enumerate(value,1):
            if not isinstance(item,dict) or set(item)!={"id","type","reference"} or item.get("id")!=f"E{i}" or item.get("type") not in EVIDENCE_TYPES: raise ValueError("AQ8 shape/type invalid")
            require_text(item["reference"],"AQ8.reference")
        return value
    if qid=="AQ9":
        value=parse_json_answer(raw,qid); uids=answer_ids(state,"UI"); aids=answer_ids(state,"A"); eids=answer_ids(state,"E")
        if not isinstance(value,list) or len(value)!=len(uids): raise ValueError("AQ9 must cover every UI#")
        seen=set()
        for item in value:
            if not isinstance(item,dict) or set(item)!={"intent_id","result","action_ids","evidence_ids","remaining_gap"}: raise ValueError("AQ9 shape invalid")
            if item["intent_id"] not in uids or item["intent_id"] in seen or item["result"] not in INTENT_OUTCOMES: raise ValueError("AQ9 result invalid")
            if any(x not in aids for x in item["action_ids"]) or any(x not in eids for x in item["evidence_ids"]): raise ValueError("AQ9 references invalid")
            gap=require_text(item["remaining_gap"],"AQ9.remaining_gap",True)
            if item["result"] in {"SUCCESS","NOT_APPLICABLE"} and gap: raise ValueError("AQ9 success cannot retain a gap")
            if item["result"] in {"PARTIAL","FAILED","UNADDRESSED"} and not gap.strip(): raise ValueError("AQ9 incomplete result requires gap")
            seen.add(item["intent_id"])
        return value
    if qid=="AQ10":
        value=parse_json_answer(raw,qid)
        if not isinstance(value,dict) or set(value)!={"relationship","divergences"}: raise ValueError("AQ10 shape invalid")
        rel=value["relationship"]; has_plan=state["answers"].get("AQ5")=="YES"
        if rel not in PLAN_RELATIONSHIPS or (has_plan and rel=="NO_PRIOR_PLAN") or (not has_plan and rel!="NO_PRIOR_PLAN"): raise ValueError("AQ10 relationship invalid")
        if not isinstance(value["divergences"],list): raise ValueError("AQ10 divergences invalid")
        if rel in {"NO_PRIOR_PLAN","MATCHED"} and value["divergences"]: raise ValueError("AQ10 divergences must be empty")
        pids=answer_ids(state,"P"); aids=answer_ids(state,"A")
        for item in value["divergences"]:
            if not isinstance(item,dict) or set(item)!={"plan_ids","action_ids","cause","note"}: raise ValueError("AQ10 divergence shape invalid")
            if any(x not in pids for x in item["plan_ids"]) or not item["action_ids"] or any(x not in aids for x in item["action_ids"]): raise ValueError("AQ10 references invalid")
            if item["cause"] not in DIVERGENCE_CAUSES: raise ValueError("AQ10 cause invalid")
            note=require_text(item["note"],"AQ10.note",True)
            if item["cause"]=="OTHER" and not note.strip(): raise ValueError("AQ10 OTHER requires note")
        return value
    if qid=="AQ11":
        value=parse_json_answer(raw,qid); aids=answer_ids(state,"A")
        if not isinstance(value,list): raise ValueError("AQ11 must be an array")
        seen=set()
        for item in value:
            if not isinstance(item,dict) or set(item)!={"action_id","basis","note"}: raise ValueError("AQ11 shape invalid")
            if item["action_id"] not in aids or item["action_id"] in seen: raise ValueError("AQ11 action_id invalid")
            if not isinstance(item["basis"],list) or not item["basis"] or any(x not in DECISION_BASES for x in item["basis"]): raise ValueError("AQ11 basis invalid")
            note=require_text(item["note"],"AQ11.note",True)
            if "OTHER" in item["basis"] and not note.strip(): raise ValueError("AQ11 OTHER requires note")
            seen.add(item["action_id"])
        return value
    if qid=="AQ12":
        value=raw.strip().upper()
        if value not in OVERALL_OUTCOMES: raise ValueError("AQ12 outcome invalid")
        return value
    if qid=="AQ13":
        value=parse_json_answer(raw,qid)
        if not isinstance(value,list): raise ValueError("AQ13 must be an array")
        for item in value:
            if not isinstance(item,dict) or set(item)!={"condition","alternate_action_type","alternate_action_subtype","note"}: raise ValueError("AQ13 shape invalid")
            require_text(item["condition"],"AQ13.condition")
            if item["alternate_action_type"] not in ACTION_SUBTYPES or item["alternate_action_subtype"] not in ACTION_SUBTYPES[item["alternate_action_type"]]: raise ValueError("AQ13 alternate action invalid")
            require_text(item["note"],"AQ13.note",True)
        return value
    if qid=="AQ14":
        text=require_text(raw,qid); positions=[text.find(h) for h in NARRATIVE_HEADINGS]
        if any(p<0 for p in positions) or positions!=sorted(positions) or not text.startswith("NARRATIVE_MAPPING"): raise ValueError("AQ14 headings invalid")
        known=answer_ids(state,"UI")|answer_ids(state,"A")|answer_ids(state,"P")|answer_ids(state,"E")
        refs=set(re.findall(r"\b(?:UI|A|P|E)[1-9][0-9]*\b",text))
        if refs-known: raise ValueError("AQ14 introduces unknown identifiers")
        if answer_ids(state,"UI")-refs or answer_ids(state,"A")-refs: raise ValueError("AQ14 must reference every UI# and A#")
        if state["answers"].get("AQ5")=="YES" and answer_ids(state,"P")-refs: raise ValueError("AQ14 must reference every P#")
        if state["answers"].get("AQ5")=="NO" and "NO_PRIOR_PLAN" not in text: raise ValueError("AQ14 must state NO_PRIOR_PLAN")
        return text
    raise ValueError(f"unknown action question: {qid}")

def ask_json(obj:dict[str,Any])->str:
    print(json.dumps(obj,ensure_ascii=False),flush=True)
    line=sys.stdin.readline()
    if line=="": raise EOFError("protocol answer input ended")
    return line.rstrip("\n")

def run_action_questionnaire()->dict[str,Any]:
    state={"answers":{}}
    for index,spec in enumerate(ACTION_QUESTIONS):
        question={**spec,"status":"QUESTION","protocol":"action_questioner","question_number":index+1,"question_count":len(ACTION_QUESTIONS)}
        while True:
            raw=ask_json(question)
            try:
                state["answers"][spec["id"]]=validate_action_answer(spec["id"],raw,state)
                break
            except Exception as exc:
                question={**question,"error":type(exc).__name__,"detail":str(exc)}
    pairs=[{"id":spec["id"],"question":spec["question"],"answer":state["answers"][spec["id"]]} for spec in ACTION_QUESTIONS]
    return {"state":state,"action":{"action_type":"action_questionnaire","scope":"worker","pairs":pairs}}

def router_norm(qid:str,raw:str)->str:
    raw=raw.strip()
    if qid=="Q15.1": return "NONE" if raw.upper() in {"NONE","NO FACT","NO_OBSERVABLE_FACT"} else raw
    key=raw.upper()
    aliases={"Y":"YES","N":"NO","ONLY THIS PATH":"ONLY_THIS_PATH","THIS PATH":"ONLY_THIS_PATH","PATH ONLY":"ONLY_THIS_PATH","PREVENTS RESULT":"PREVENTS_RESULT","TASK WIDE":"PREVENTS_RESULT","UNSURE":"UNKNOWN","DON'T KNOW":"UNKNOWN","DONT KNOW":"UNKNOWN"}
    return aliases.get(key,key)

def router_validate(qid:str,answer:str)->None:
    allowed=ROUTER_Q[qid][1]
    if allowed==["FREE_TEXT_OR_NONE"]:
        if not answer.strip(): raise ValueError("Q15.1 requires a fact or NONE")
    elif answer not in allowed:
        raise ValueError(f"allowed answers: {allowed}")

def router_question(qid:str,trace:list[dict[str,Any]])->dict[str,Any]:
    text,allowed=ROUTER_Q[qid]
    return {"status":"QUESTION","protocol":"end_turn_router","question_id":qid,"question":text,"allowed_answers":allowed,"trace":[x for x in trace if x.get("kind")=="answer"]}

def router_transition(qid:str,a:str,stopping_fact:str|None)->tuple[str,str|None,str|None]:
    key=f"{qid}:{a}"
    if key in CONTINUE_INSTRUCTIONS: return "DIRECTIVE","CONTINUE",CONTINUE_INSTRUCTIONS[key]
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
    if qid=="Q15.1" and a!="NONE": return "QUESTION","Q15.2",None
    if (qid,a) in routes: return "QUESTION",routes[(qid,a)],None
    if qid in ALT_NEXT and a=="NO": return "QUESTION",ALT_NEXT[qid],None
    if qid=="A9" and a=="NO": return "QUESTION","I1",None
    if qid=="I5" and a=="NO": return "DIRECTIVE","IMPASSE","A required dependency remains unsatisfied; applicable alternatives are exhausted; no independent requested work or available gap-reducing action remains."
    if qid=="C4" and a=="YES": return "DIRECTIVE","COMPLETE","The questionnaire found no remaining continuation trigger and the Completion Evidence Test is satisfied."
    raise RuntimeError(f"Unhandled router transition {qid}/{a}")

def run_router()->dict[str,Any]:
    qid="Q1"; trace=[]; stopping_fact=None
    while True:
        question=router_question(qid,trace)
        while True:
            raw=ask_json(question)
            a=router_norm(qid,raw)
            try:
                router_validate(qid,a); break
            except Exception as exc:
                question={**question,"error":type(exc).__name__,"detail":str(exc)}
        trace.append({"kind":"answer","question_id":qid,"answer":a})
        if qid=="Q15.1" and a!="NONE": stopping_fact=a
        kind,target,instruction=router_transition(qid,a,stopping_fact)
        if kind=="QUESTION":
            qid=target
            continue
        pairs=[{"id":x["question_id"],"question":ROUTER_Q[x["question_id"]][0],"answer":x["answer"]} for x in trace]
        cycle={"cycle_id":uuid.uuid4().hex,"scope":"worker","pairs":pairs,"directive":target}
        if instruction: cycle["instruction"]=instruction
        if target=="IMPASSE": cycle["impasse_evidence"]=stopping_fact or "No additional impasse evidence was captured beyond the recorded router answers."
        return cycle

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

def parse_initialization(value:Any)->str:
    if not isinstance(value,dict) or set(value)!={"schema","type","user_prompt"}:
        raise ValueError("initialization object must contain exactly schema, type, and user_prompt")
    if value.get("schema")!=INITIALIZATION_SCHEMA:
        raise ValueError("initialization schema is invalid")
    if value.get("type")!="INITIALIZE":
        raise ValueError("initialization type must be INITIALIZE")
    return require_text(value.get("user_prompt"),"initialization.user_prompt")

def process_initialization(value:Any)->dict[str,Any]:
    user_prompt=parse_initialization(value)
    state=new_state(user_prompt)
    return issue_task_payload(
        state,
        "Execute exactly one material next action toward task_prompt. Return this complete payload unchanged when that action completes, fails, or reaches an attempted end-of-turn stop point.",
        {"initialization":"accepted","prompt_intake_mode":state["prompt_intake_mode"]},
    )

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
