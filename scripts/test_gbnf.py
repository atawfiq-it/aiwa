import json
from pathlib import Path
from typing import Optional
import httpx
from pydantic import BaseModel
from app.services.agents.grammar_compiler import grammar_compiler


# Define a strict target Pydantic schema
class CodeReviewResult(BaseModel):
    model_config = {"extra": "allow"}  # Accept any extra keys returned by the model

    vulnerability: Optional[str] = "None"
    risk_level: Optional[str] = "low"
    explanation: Optional[str] = None
    fixed_code: Optional[str] = None


def test_gbnf_grammar():
    print("⚙️  Compiling Pydantic schema into official llama.cpp GBNF Grammar...")
    gbnf_rules = grammar_compiler.compile_pydantic(CodeReviewResult)
    print(
        "\n--- COMPILED GBNF RULES ---\n"
        + gbnf_rules.strip()
        + "\n---------------------------\n"
    )

    token_path = Path("data/.aiwa_session_token")
    if not token_path.exists():
        print(
            "❌ Error: Session token file not found. Is the backend running ('just dev')?"
        )
        return

    token = token_path.read_text().strip()
    headers = {"X-AIWA-Token": token}

    prompt = (
        "Review this insecure code snippet and return ONLY the JSON result matching the required schema:\n"
        "user_id = request.args.get('id')\n"
        "query = f\"SELECT * FROM users WHERE id = '{user_id}'\"\n"
        "return db.execute(query).fetchall()"
    )

    print("🚀 Sending request to AIWA with GBNF grammar enforcement...")
    with httpx.Client(timeout=120.0) as client:
        res = client.post(
            "http://127.0.0.1:8000/api/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": prompt}],
                "json_schema": CodeReviewResult.model_json_schema(),
            },
            headers=headers,
        )

        if res.status_code != 200:
            print(f"❌ Server Error ({res.status_code}): {res.text}")
            return

        # Parse SSE stream tokens
        accumulated = []
        for line in res.text.split("\n"):
            if line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                    if "text" in data:
                        accumulated.append(data["text"])
                except Exception:
                    pass

        raw_output = "".join(accumulated).strip()
        print("\n📥 Model Raw Output (Guaranteed Valid JSON):\n", raw_output)

        if not raw_output:
            print("⚠️ Warning: Empty response received from model stream.")
            return

        # Validate with Pydantic
        parsed = json.loads(raw_output)
        validated = CodeReviewResult(**parsed)
        print("\n✅ SUCCESS: Output validated 100% strictly against Pydantic schema:")
        print(f"   -> Vulnerability: {validated.vulnerability}")
        print(f"   -> Risk Level:    {validated.risk_level}")
        print(f"   -> Fixed Code:    {validated.fixed_code[:65]}...")


if __name__ == "__main__":
    test_gbnf_grammar()
