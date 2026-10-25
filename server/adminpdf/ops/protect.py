"""Encryption and permissions."""

from __future__ import annotations

import secrets

import pymupdf

from ..core.errors import UserError
from ..core.pdf import open_pdf, require_owner, save_pdf
from .base import Context, Field, Operation, Params, register


class EncryptParams(Params):
    user_password: str = Field(
        "",
        tr="Açma şifresi",
        en="Open password",
        help_tr="Boş bırakılırsa PDF şifresiz açılır ama izinler uygulanır.",
        help_en="If empty, the PDF opens without a password but permissions still apply.",
        max_length=128,
        ui={"widget": "password"},
    )
    owner_password: str = Field(
        "",
        tr="İzin (sahip) şifresi",
        en="Permissions (owner) password",
        help_tr="Boş bırakılırsa rastgele, güçlü bir şifre üretilir.",
        help_en="If empty, a strong random password is generated.",
        max_length=128,
        ui={"widget": "password"},
    )
    allow_print: bool = Field(True, tr="Yazdırmaya izin ver", en="Allow printing")
    allow_copy: bool = Field(False, tr="Kopyalamaya izin ver", en="Allow copying")
    allow_modify: bool = Field(False, tr="Değiştirmeye izin ver", en="Allow editing")
    allow_annotate: bool = Field(True, tr="Yorum ve form doldurmaya izin ver", en="Allow comments and form filling")


@register
class Encrypt(Operation):
    name = "encrypt"
    category = "protect"
    title_tr, title_en = "Şifrele", "Protect with Password"
    description_tr = "AES-256 ile şifreler ve yazdırma/kopyalama/düzenleme izinlerini ayarlar."
    description_en = "Encrypt with AES-256 and set print / copy / edit permissions."
    Params = EncryptParams

    def run(self, ctx: Context, params: EncryptParams) -> None:
        owner = params.owner_password or secrets.token_urlsafe(24)
        if owner == params.user_password:
            # Same password grants owner rights, which silently voids every
            # permission flag.
            raise UserError(
                "İzin şifresi açma şifresiyle aynı olamaz.",
                "The permissions password must differ from the open password.",
            )
        perm = pymupdf.PDF_PERM_ACCESSIBILITY
        if params.allow_print:
            perm |= pymupdf.PDF_PERM_PRINT | pymupdf.PDF_PERM_PRINT_HQ
        if params.allow_copy:
            perm |= pymupdf.PDF_PERM_COPY
        if params.allow_modify:
            perm |= pymupdf.PDF_PERM_MODIFY | pymupdf.PDF_PERM_ASSEMBLE
        if params.allow_annotate:
            perm |= pymupdf.PDF_PERM_ANNOTATE | pymupdf.PDF_PERM_FORM
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            require_owner(doc, inp.password)
            save_pdf(
                doc,
                ctx.output(f"{inp.stem}_sifreli.pdf"),
                encryption=pymupdf.PDF_ENCRYPT_AES_256,
                user_pw=params.user_password,
                owner_pw=owner,
                permissions=perm,
            )


@register
class Decrypt(Operation):
    name = "decrypt"
    category = "protect"
    title_tr, title_en = "Şifre Kaldır", "Remove Password"
    description_tr = "Şifreyi ve kısıtlamaları kaldırır (dosyanın şifresini bilmeniz gerekir)."
    description_en = "Remove the password and restrictions (you must know the password)."

    def run(self, ctx: Context, params: object) -> None:
        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password) as doc:
            require_owner(doc, inp.password)
            save_pdf(doc, ctx.output(f"{inp.stem}_sifresiz.pdf"), encryption=pymupdf.PDF_ENCRYPT_NONE)
