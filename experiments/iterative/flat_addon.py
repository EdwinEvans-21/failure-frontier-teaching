from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from experiments.pilot.provenance_ff import FailureFrontierRecord, sha256_text


LINEAGE_FLAT_ADDON_RENDERER_VERSION = "lineage_flat_analysis_renderer_v1"


@dataclass(frozen=True)
class LineageFlatAddonBlock:
    ordinal: int
    entry_kind: str
    text: str
    source_identity: str | None
    source_sha256: str | None

    @property
    def sha256(self) -> str:
        return sha256_text(self.text)


@dataclass(frozen=True)
class RenderedLineageFlatAddon:
    text: str
    blocks: tuple[LineageFlatAddonBlock, ...]
    renderer_version: str = LINEAGE_FLAT_ADDON_RENDERER_VERSION

    @property
    def sha256(self) -> str:
        return sha256_text(self.text)

    def manifest(self) -> dict[str, Any]:
        return {
            "renderer_version": self.renderer_version,
            "sha256": self.sha256,
            "block_count": len(self.blocks),
            "blocks": [
                {
                    "ordinal": block.ordinal,
                    "entry_kind": block.entry_kind,
                    "sha256": block.sha256,
                    "source_identity": block.source_identity,
                    "source_sha256": block.source_sha256,
                }
                for block in self.blocks
            ],
        }


def _inference_text(ordinal: int, item: Any) -> str:
    return "\n".join((
        f"Analysis item {ordinal}",
        f"Claim: {item.claim}",
        f"Evidence: {item.evidence}",
        "Evidence sources: " + " | ".join(item.evidence_sources),
        f"Reproducibility note: {item.reproducibility_note}",
    ))


def _excerpt_text(ordinal: int, item: Any) -> str:
    return "\n".join((
        f"Analysis item {ordinal}",
        f"Origin: {item.source_type}",
        f"Source artifact: {item.source_artifact}",
        f"Source SHA-256: {item.source_sha256}",
        f"Exact excerpt: {item.exact_source_excerpt}",
    ))


def _hypothesis_text(ordinal: int, item: Any) -> str:
    return "\n".join((
        f"Analysis item {ordinal}",
        "Origin: FF_ORGANIZER",
        f"Hypothesis: {item.hypothesis}",
        f"Evidence limitation: {item.evidence_limitation}",
    ))


def render_lineage_flat_analysis(
    record_value: FailureFrontierRecord | dict[str, Any],
) -> RenderedLineageFlatAddon:
    """Render accepted structured-record entries without confidence-tier framing.

    The function never reads historical rendered Markdown. It preserves every
    substantive field selected below byte-for-byte and in registered order.
    Confidence and support metadata are omitted by field selection, not by
    editing or filtering entry text.
    """
    record = (
        record_value
        if isinstance(record_value, FailureFrontierRecord)
        else FailureFrontierRecord.from_dict(record_value)
    )
    blocks: list[LineageFlatAddonBlock] = []
    ordinal = 0
    for item in record.evidence_grounded_inferences:
        ordinal += 1
        blocks.append(LineageFlatAddonBlock(
            ordinal, "inference", _inference_text(ordinal, item),
            "FF_ORGANIZER", None,
        ))
    for item in record.selected_low_confidence_excerpts:
        ordinal += 1
        blocks.append(LineageFlatAddonBlock(
            ordinal, "exact_excerpt", _excerpt_text(ordinal, item),
            item.source_artifact, item.source_sha256,
        ))
    for item in record.organizer_hypotheses:
        ordinal += 1
        blocks.append(LineageFlatAddonBlock(
            ordinal, "organizer_hypothesis", _hypothesis_text(ordinal, item),
            "FF_ORGANIZER", None,
        ))
    if not blocks:
        raise ValueError("validated provenance record has no accepted entries")
    rendered = RenderedLineageFlatAddon(
        text="\n\n".join(block.text for block in blocks).rstrip() + "\n",
        blocks=tuple(blocks),
    )
    audit_lineage_flat_analysis(record, rendered)
    return rendered


def audit_lineage_flat_analysis(
    record: FailureFrontierRecord,
    rendered: RenderedLineageFlatAddon,
) -> None:
    expected_kinds = (
        ["inference"] * len(record.evidence_grounded_inferences)
        + ["exact_excerpt"] * len(record.selected_low_confidence_excerpts)
        + ["organizer_hypothesis"] * len(record.organizer_hypotheses)
    )
    if [block.entry_kind for block in rendered.blocks] != expected_kinds:
        raise ValueError("lineage Flat add-on entry order drift")
    if [block.ordinal for block in rendered.blocks] != list(
            range(1, len(rendered.blocks) + 1)):
        raise ValueError("lineage Flat add-on ordinal drift")

    structural_text = "\n".join(
        line for block in rendered.blocks for line in block.text.splitlines()
        if not line.startswith((
            "Claim: ", "Evidence: ", "Reproducibility note: ",
            "Exact excerpt: ", "Hypothesis: ", "Evidence limitation: ",
        ))
    )
    forbidden_structure = (
        "DIRECT_FACT", "EVIDENCE_GROUNDED_INFERENCE",
        "LOW_CONFIDENCE_HYPOTHESIS", "PROVISIONALLY_SUPPORTED",
        "PARTIALLY_SUPPORTED", "confidence", "trust boundary",
        "provenance-stratified",
    )
    lowered = structural_text.lower()
    if any(token.lower() in lowered for token in forbidden_structure):
        raise ValueError("lineage Flat add-on contains forbidden structural framing")

    for item, block in zip(record.evidence_grounded_inferences, rendered.blocks):
        for exact in (item.claim, item.evidence, item.reproducibility_note):
            if exact not in block.text:
                raise ValueError("inference substantive text was changed")
    offset = len(record.evidence_grounded_inferences)
    for item, block in zip(
            record.selected_low_confidence_excerpts, rendered.blocks[offset:]):
        if item.exact_source_excerpt not in block.text:
            raise ValueError("exact excerpt substantive text was changed")
    offset += len(record.selected_low_confidence_excerpts)
    for item, block in zip(record.organizer_hypotheses, rendered.blocks[offset:]):
        if item.hypothesis not in block.text or item.evidence_limitation not in block.text:
            raise ValueError("organizer hypothesis substantive text was changed")


def audit_addon_excludes_complete_sources(
    rendered: RenderedLineageFlatAddon, *, parent_code: str,
    raw_source_contents: tuple[str, ...],
) -> None:
    if parent_code and parent_code in rendered.text:
        raise ValueError("lineage Flat add-on duplicates complete parent code")
    for content in raw_source_contents:
        if content and content in rendered.text:
            raise ValueError("lineage Flat add-on duplicates a complete raw source")
