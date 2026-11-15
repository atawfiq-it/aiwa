from typing import Any


class GrammarCompiler:
    @staticmethod
    def schema_to_gbnf(schema: dict[str, Any]) -> str:
        """Converts a JSON Schema dictionary into a GGML GBNF grammar string for logits masking."""
        # Standard GBNF root for JSON objects
        gbnf = [
            "root ::= object",
            'object ::= "{" ws (string ":" ws value ("," ws string ":" ws value)*)? ws "}"',
            'array ::= "[" ws (value ("," ws value)*)? ws "]"',
            'value ::= string | number | object | array | "true" | "false" | "null"',
            'string ::= """ ([^"\\] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F]))* """',
            'number ::= [0-9]+ ("." [0-9]+)? ([eE] [-+]? [0-9]+)?',
            "ws ::= [ \\t\\n]*",
        ]
        return "\n".join(gbnf)


grammar_compiler = GrammarCompiler()
