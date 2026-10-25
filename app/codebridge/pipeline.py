
"""End-to-end CodeBridge source analysis and translation pipeline."""

from typing import Any

from codebridge.analyzer import analyze_source
from codebridge.ir import source_to_ir
from codebridge.parser import parse_source
from codebridge.translator import translate_ir
from codebridge.python_translator import translate_ir_to_python


def process_source(source: str) -> dict[str, Any]:
    """Analyze source and generate supported pseudocode and Python."""
    if not isinstance(source, str):
        raise TypeError("source must be a string")

    parse_report = parse_source(source)
    analysis_report = analyze_source(source)

    result: dict[str, Any] = {
        "tool": "CodeBridge",
        "version": "0.2.0",
        "status": "analysis_complete",
        "parse": parse_report,
        "analysis": analysis_report,
        "ir": None,
        "translation": None,
        "python_translation": None,
        "translation_error": None,
    }

    try:
        ir = source_to_ir(source)
        pseudocode = translate_ir(ir)
        python_translation = translate_ir_to_python(ir)

        result["ir"] = ir
        result["translation"] = pseudocode
        result["python_translation"] = python_translation
        result["status"] = "translation_complete"

    except ValueError as exc:
        result["status"] = "analysis_complete_translation_unsupported"
        result["translation_error"] = str(exc)

    return result
