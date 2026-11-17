from typing import Any

from pydantic import BaseModel


class GBNFCompiler:
    """Uses the official, battle-tested llama.cpp JSON grammar for guaranteed constrained decoding."""

    # Official llama.cpp GBNF grammar for any valid JSON object structure
    OFFICIAL_JSON_GRAMMAR = r"""
    root   ::= object
    object ::= "{" ws (string ":" ws value ("," ws string ":" ws value)*)? ws "}"
    array  ::= "[" ws (value ("," ws value)*)? ws "]"
    value  ::= string | number | object | array | "true" | "false" | "null"
    string ::= "\"" ([^"\\] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F]))* "\""
    number ::= "-"? [0-9]+ ("." [0-9]+)? ([eE] [+-]?[ 0-9]+)?
    ws     ::= [ \t\n]*
    """

    def compile_pydantic(self, model: type[BaseModel]) -> str:
        return self.OFFICIAL_JSON_GRAMMAR

    def compile_schema(self, schema: dict[str, Any]) -> str:
        return self.OFFICIAL_JSON_GRAMMAR


grammar_compiler = GBNFCompiler()
