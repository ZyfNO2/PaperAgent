from __future__ import annotations

import re
from dataclasses import dataclass

_ROLE_SUFFIX = re.compile(r"\s*\[declared role:[^\]]+\]\s*$", re.IGNORECASE)
_TOKEN = re.compile(r"[A-Za-z0-9]+|[\u3400-\u9fff]+")
_GENERIC_TOKENS = {
    "a",
    "an",
    "attachment",
    "document",
    "file",
    "for",
    "from",
    "i",
    "material",
    "my",
    "paper",
    "provided",
    "reference",
    "supplied",
    "the",
    "uploaded",
    "user",
    "users",
}
_GENERIC_CJK = ("上传的论文", "提供的论文", "用户材料", "附件论文", "这篇论文")


@dataclass(frozen=True)
class UserMaterialIdentity:
    index: int
    reference: str
    title: str
    identifiable: bool

    @property
    def gap_id(self) -> str:
        return f"user-material-{self.index:02d}-identity"

    @property
    def query_id(self) -> str:
        return f"user-material-{self.index:02d}-lookup"


def material_title(reference: str) -> str:
    return _ROLE_SUFFIX.sub("", reference).strip()


def is_identifiable_public_title(title: str) -> bool:
    """Return whether a material reference resembles a searchable public title.

    The check is form-based and domain-independent. Generic upload placeholders remain
    unidentifiable; distinctive multi-token titles, model identifiers, and substantial CJK titles
    can proceed to exact-title public verification.
    """

    normalized = " ".join(title.split())
    if not normalized:
        return False
    if any(phrase in normalized for phrase in _GENERIC_CJK):
        return False
    tokens = _TOKEN.findall(normalized)
    discriminative = [token for token in tokens if token.casefold() not in _GENERIC_TOKENS]
    has_identifier = any(
        any(character.isdigit() for character in token)
        or (any(character.isupper() for character in token) and any(character.islower() for character in token))
        or (len(token) >= 3 and token.isupper())
        for token in discriminative
    )
    has_cjk_title = any("\u3400" <= character <= "\u9fff" for character in normalized) and len(
        normalized.replace(" ", "")
    ) >= 8
    return len(discriminative) >= 3 or (len(tokens) >= 3 and has_identifier) or has_cjk_title


def user_material_identities(references: list[str] | tuple[str, ...]) -> tuple[UserMaterialIdentity, ...]:
    return tuple(
        UserMaterialIdentity(
            index=index,
            reference=reference,
            title=title,
            identifiable=is_identifiable_public_title(title),
        )
        for index, reference in enumerate(references, start=1)
        for title in (material_title(reference),)
    )


__all__ = [
    "UserMaterialIdentity",
    "is_identifiable_public_title",
    "material_title",
    "user_material_identities",
]
