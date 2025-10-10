import argparse
import json
import pathlib
import sys
import uuid
from typing import Any, Dict

import boto3


def build_payload(input_csv_text: str, max_concurrent_rows: int, wrap_under_input: bool) -> str:
    """Build the AgentCore payload string.

    If wrap_under_input=True, sends {"input": {...}}. Otherwise sends top-level keys.
    """
    if wrap_under_input:
        body: Dict[str, Any] = {
            "input": {
                "input_csv": input_csv_text,
                "max_concurrent_rows": max_concurrent_rows,
            }
        }
    else:
        body = {
            "input_csv": input_csv_text,
            "max_concurrent_rows": max_concurrent_rows,
        }
    return json.dumps(body)


def parse_response(raw_bytes: bytes) -> Dict[str, Any]:
    """Parse the AgentCore response stream and extract the output object."""
    try:
        payload_json = json.loads(raw_bytes.decode("utf-8"))
    except Exception:
        # Fallback: return opaque payload
        return {"raw": raw_bytes.decode("utf-8", errors="replace")}

    # Some runtimes wrap return as {"output": {...}}. Support both.
    if isinstance(payload_json, dict) and "output" in payload_json:
        output = payload_json["output"]
        if isinstance(output, str):
            try:
                return json.loads(output)
            except Exception:
                return {"output": output}
        return output

    return payload_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Invoke an AWS AgentCore runtime with a CSV input and save the output CSV.")
    parser.add_argument("--agent-arn", "-a", required=True, help="AgentCore runtime ARN (agentRuntimeArn)")
    parser.add_argument("--region", "-r", default="us-west-2", help="AWS region (default: us-west-2)")
    parser.add_argument("--qualifier", "-q", default="DEFAULT", help="Agent qualifier (default: DEFAULT)")
    parser.add_argument("--input", "-i", default=str(pathlib.Path(__file__).with_name("input.csv")), help="Path to input CSV (default: deploy/input.csv)")
    parser.add_argument("--output", "-o", default=str(pathlib.Path.cwd() / "output.csv"), help="Path to save output CSV (default: ./output.csv)")
    parser.add_argument("--max-concurrent-rows", "-m", type=int, default=20, help="Max concurrent rows (default: 20)")
    parser.add_argument("--wrap-input", action="store_true", help="Wrap payload under 'input' (use after redeploying updated handler)")

    args = parser.parse_args()

    input_path = pathlib.Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input CSV not found: {input_path}", file=sys.stderr)
        return 2

    input_csv_text = input_path.read_text(encoding="utf-8")

    client = boto3.client("bedrock-agentcore", region_name=args.region)

    # Must be 33+ chars; use a long UUID-based session id
    runtime_session_id = f"session-{uuid.uuid4().hex}-{uuid.uuid4().hex}"

    payload = build_payload(
        input_csv_text=input_csv_text,
        max_concurrent_rows=args.max_concurrent_rows,
        wrap_under_input=args.wrap_input,
    )

    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=args.agent_arn,
            runtimeSessionId=runtime_session_id,
            payload=payload,
            qualifier=args.qualifier,
        )
    except Exception as e:
        print(f"ERROR: Invoke failed: {e}", file=sys.stderr)
        return 3

    try:
        raw = response["response"].read()
    except Exception as e:
        print(f"ERROR: Failed reading response stream: {e}", file=sys.stderr)
        return 4

    result_obj = parse_response(raw)

    # Expecting our app to return { 'output_csv': '...', 'rows_processed': N, 'status': 'success' }
    output_csv = None
    if isinstance(result_obj, dict):
        output_csv = result_obj.get("output_csv")

    if not output_csv:
        # Write the full JSON response for troubleshooting
        fallback_path = pathlib.Path(args.output).with_suffix(".json")
        fallback_path.write_text(json.dumps(result_obj, indent=2), encoding="utf-8")
        print(f"WARNING: No 'output_csv' found. Wrote full response JSON to: {fallback_path}")
        return 0

    out_path = pathlib.Path(args.output)
    out_path.write_text(output_csv, encoding="utf-8")
    print(f"Saved output CSV to: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


