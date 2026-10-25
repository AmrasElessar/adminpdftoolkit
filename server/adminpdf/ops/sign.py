"""Digital signatures: PAdES signing, verification, self-signed certificates.

Signing appends an incremental update with pyHanko, so earlier signatures and
the original bytes stay untouched. Verification never fetches anything: no
OCSP/CRL, no AIA chasing — trust is decided against the system's root store
only, and the report says so plainly when a chain does not reach it.
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import io
import logging
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal

import pymupdf
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from ..core.errors import UserError
from ..core.pdf import open_pdf, unicode_font_path
from .base import Context, Field, FileParam, Operation, Params, register
from .forms import TYPE_NAMES, FormIndex, within

MAX_CERT_BYTES = 1_000_000
MAX_SIGNATURES = 200
_TOKEN_RE = re.compile(r"\{(name|date|reason|location)\}")
# RFC 9336 id-kp-documentSigning, plus Microsoft's older document-signing OID
# that Acrobat and Windows also recognise.
_EKU_DOCUMENT_SIGNING = x509.ObjectIdentifier("1.3.6.1.5.5.7.3.36")
_EKU_MS_DOCUMENT_SIGNING = x509.ObjectIdentifier("1.3.6.1.4.1.311.10.3.12")


@contextlib.contextmanager
def _quiet_pyhanko() -> Iterator[None]:
    """pyHanko logs a full traceback for every untrusted chain — the normal
    case for self-signed certificates — which would drown the server log."""
    log = logging.getLogger("pyhanko")
    previous = log.level
    log.setLevel(logging.CRITICAL)
    try:
        yield
    finally:
        log.setLevel(previous)


# -- certificates ----------------------------------------------------------------
def _name_attr(name: x509.Name, oid: x509.ObjectIdentifier) -> str:
    attrs = name.get_attributes_for_oid(oid)
    return str(attrs[0].value) if attrs else ""


def load_pkcs12(path: Path, password: str) -> tuple[Any, x509.Certificate]:
    """Open a PKCS#12 bundle → (pyHanko signer, certificate).

    ``cryptography`` parses it first so a wrong password is told apart from
    a damaged file, and an expired certificate is refused up front instead
    of producing a signature every viewer marks invalid.
    """
    from pyhanko.sign import signers

    data = path.read_bytes()
    if len(data) > MAX_CERT_BYTES:
        raise UserError("Sertifika dosyası çok büyük.", "The certificate file is too large.")
    try:
        key, cert, _extra = pkcs12.load_key_and_certificates(data, password.encode() or None)
    except ValueError as e:
        msg = str(e).lower()
        if "password" in msg or "mac" in msg or "decrypt" in msg:
            raise UserError(
                "Sertifika şifresi yanlış.",
                "The certificate password is wrong.",
            ) from e
        raise UserError(
            "Sertifika dosyası okunamadı (.p12/.pfx PKCS#12 bekleniyor).",
            "Cannot read the certificate file (expected a .p12/.pfx PKCS#12 bundle).",
        ) from e
    if key is None or cert is None:
        raise UserError(
            "Sertifika dosyasında özel anahtar veya sertifika yok.",
            "The certificate file has no private key or no certificate.",
        )
    now = _dt.datetime.now(_dt.UTC)
    if not cert.not_valid_before_utc <= now <= cert.not_valid_after_utc:
        until = cert.not_valid_after_utc.strftime("%d.%m.%Y")
        raise UserError(
            f"Sertifika geçerlilik süresi dışında (bitiş: {until}).",
            f"The certificate is outside its validity period (expires: {until}).",
        )
    signer = signers.SimpleSigner.load_pkcs12(  # type: ignore[no-untyped-call]
        str(path), passphrase=password.encode() or None
    )
    if signer is None:
        raise UserError("Sertifika yüklenemedi.", "Cannot load the certificate.")
    return signer, cert


class CertificateParams(Params):
    common_name: str = Field(
        ...,
        tr="Ad Soyad / Ortak ad (CN)",
        en="Name / Common name (CN)",
        min_length=1,
        max_length=64,
    )
    organisation: str = Field("", tr="Kurum (O)", en="Organisation (O)", max_length=64)
    email: str = Field(
        "",
        tr="E-posta",
        en="Email",
        max_length=128,
        pattern=r"^$|^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    country: str = Field("TR", tr="Ülke kodu (C)", en="Country code (C)", pattern=r"^[A-Za-z]{2}$")
    validity_years: int = Field(3, tr="Geçerlilik (yıl)", en="Validity (years)", ge=1, le=10)
    key_type: Literal["rsa", "ec"] = Field(
        "rsa",
        tr="Anahtar türü",
        en="Key type",
        ui={
            "options": {
                "rsa": {"tr": "RSA 3072 (en uyumlu)", "en": "RSA 3072 (most compatible)"},
                "ec": {"tr": "ECDSA P-256 (kısa, hızlı)", "en": "ECDSA P-256 (compact, fast)"},
            }
        },
    )
    password: str = Field(
        ...,
        tr="Sertifika şifresi",
        en="Certificate password",
        help_tr="Sertifikayı her imzalamada bu şifreyle açacaksınız.",
        help_en="You will unlock the certificate with this password every time you sign.",
        min_length=6,
        max_length=128,
        ui={"widget": "password"},
    )


@register
class CreateCertificate(Operation):
    name = "create_certificate"
    category = "sign"
    title_tr, title_en = "İmza Sertifikası Oluştur", "Create Signing Certificate"
    description_tr = (
        "Kendinden imzalı bir dijital imza sertifikası (.p12) üretir. Kurum içi kullanım içindir; "
        "e-imza (nitelikli elektronik sertifika) yerine geçmez."
    )
    description_en = (
        "Generate a self-signed digital signing certificate (.p12). Meant for internal use; "
        "it is not a qualified electronic signature certificate."
    )
    accepts = frozenset()
    min_inputs = 0
    max_inputs = 0
    Params = CertificateParams

    def run(self, ctx: Context, params: CertificateParams) -> None:
        key: rsa.RSAPrivateKey | ec.EllipticCurvePrivateKey
        if params.key_type == "ec":
            key = ec.generate_private_key(ec.SECP256R1())
        else:
            key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        ctx.progress(0.5, "")
        attrs = [x509.NameAttribute(NameOID.COMMON_NAME, params.common_name.strip())]
        if params.organisation.strip():
            attrs.append(x509.NameAttribute(NameOID.ORGANIZATION_NAME, params.organisation.strip()))
        if params.email:
            attrs.append(x509.NameAttribute(NameOID.EMAIL_ADDRESS, params.email))
        attrs.append(x509.NameAttribute(NameOID.COUNTRY_NAME, params.country.upper()))
        subject = x509.Name(attrs)
        now = _dt.datetime.now(_dt.UTC)
        builder = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - _dt.timedelta(minutes=5))
            .not_valid_after(now + _dt.timedelta(days=365 * params.validity_years))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=True,  # a.k.a. nonRepudiation
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage(
                    [_EKU_DOCUMENT_SIGNING, _EKU_MS_DOCUMENT_SIGNING, ExtendedKeyUsageOID.EMAIL_PROTECTION]
                ),
                critical=False,
            )
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        )
        if params.email:
            builder = builder.add_extension(
                x509.SubjectAlternativeName([x509.RFC822Name(params.email)]), critical=False
            )
        cert = builder.sign(key, hashes.SHA256())
        encryption = (
            serialization.PrivateFormat.PKCS12.encryption_builder()
            .kdf_rounds(100_000)
            .key_cert_algorithm(pkcs12.PBES.PBESv2SHA256AndAES256CBC)
            .hmac_hash(hashes.SHA256())
            .build(params.password.encode())
        )
        blob = pkcs12.serialize_key_and_certificates(params.common_name.strip().encode(), key, cert, None, encryption)
        ctx.output(f"{params.common_name.strip()}.p12").write_bytes(blob)
        ctx.data = {
            "subject": subject.rfc4514_string(),
            "not_after": cert.not_valid_after_utc.isoformat(),
            "sha256": cert.fingerprint(hashes.SHA256()).hex(":").upper(),
        }


# -- signing ---------------------------------------------------------------------
class SignParams(Params):
    certificate: str = FileParam(
        tr="Sertifika (.p12 / .pfx)",
        en="Certificate (.p12 / .pfx)",
        accept=["cert"],
    )
    certificate_password: str = Field(
        "", tr="Sertifika şifresi", en="Certificate password", max_length=256, ui={"widget": "password"}
    )
    reason: str = Field("", tr="İmza nedeni", en="Reason", max_length=200)
    location: str = Field("", tr="Yer", en="Location", max_length=200)
    contact: str = Field("", tr="İletişim", en="Contact", max_length=200)
    field_name: str = Field(
        "Signature1",
        tr="İmza alanı adı",
        en="Signature field name",
        help_tr="Bu adla boş bir imza alanı varsa imza oraya atılır.",
        help_en="If an empty signature field with this name exists, the signature goes there.",
        min_length=1,
        max_length=128,
        pattern=r"^[^.\x00-\x1f]+$",
    )
    visible: bool = Field(True, tr="Görünür imza", en="Visible signature")
    page: str = Field(
        "last",
        tr="Sayfa",
        en="Page",
        help_tr="Sayfa numarası veya 'last' (son sayfa).",
        help_en="Page number or 'last'.",
        pattern=r"^(last|son|[1-9][0-9]{0,5})$",
        ui={"show_if": {"visible": True}},
    )
    rect: list[float] | None = Field(
        None,
        tr="Konum [x0, y0, x1, y1]",
        en="Position [x0, y0, x1, y1]",
        help_tr="PDF birimi, sol alt köşe başlangıç. Boş = sağ alt köşe.",
        help_en="PDF units, origin bottom-left. Empty = bottom-right corner.",
        min_length=4,
        max_length=4,
        ui={"widget": "json", "show_if": {"visible": True}},
    )
    appearance_text: str = Field(
        "Dijital olarak imzalayan:\n{name}\nTarih: {date}\nNeden: {reason}\nYer: {location}",
        tr="Görünüm metni",
        en="Appearance text",
        help_tr="{name} imzalayan, {date} tarih, {reason} neden, {location} yer. Boş kalan satırlar atlanır.",
        help_en="{name} signer, {date} date, {reason} reason, {location} location. Lines left empty are dropped.",
        max_length=500,
        ui={"show_if": {"visible": True}},
    )
    signature_image: str = FileParam(
        tr="İmza görseli (isteğe bağlı)", en="Signature image (optional)", accept=["image"], required=False
    )


def render_appearance(template: str, values: dict[str, str]) -> str:
    """Replace known tokens only (never ``str.format``) and drop lines whose
    every token came out empty, so an unset reason leaves no dangling label."""
    lines: list[str] = []
    for line in template.splitlines():
        tokens = _TOKEN_RE.findall(line)
        if tokens and not any(values.get(t) for t in tokens):
            continue
        lines.append(_TOKEN_RE.sub(lambda m: values.get(m.group(1), ""), line))
    return "\n".join(lines).strip()


def _image_png(path: Path) -> tuple[bytes, float]:
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(path) as im:
            if im.width * im.height > 40_000_000:
                raise UserError("İmza görseli çok büyük.", "The signature image is too large.")
            im.load()
            rgba = im.convert("RGBA")
    except (UnidentifiedImageError, OSError) as e:
        raise UserError("İmza görseli okunamadı.", "Cannot read the signature image.") from e
    rgba.thumbnail((1200, 1200))
    buf = io.BytesIO()
    rgba.save(buf, "PNG", optimize=True)
    return buf.getvalue(), rgba.width / rgba.height


def build_stamp(out: Path, size: tuple[float, float], rotation: int, text: str, image: Path | None) -> None:
    """Draw the visible signature as a one-page PDF of the field's size.

    pyHanko embeds it as the appearance. Layout happens in the frame the
    reader sees and is mapped back to unrotated space, so the stamp reads
    upright on rotated pages too.
    """
    doc = pymupdf.open()
    page = doc.new_page(width=size[0], height=size[1])
    page.set_rotation(rotation)
    vis = page.rect
    pad = min(4.0, vis.width / 10, vis.height / 10)
    box = pymupdf.Rect(vis.x0 + pad, vis.y0 + pad, vis.x1 - pad, vis.y1 - pad)
    text_box = box
    if image is not None:
        png, ratio = _image_png(image)
        img_w = box.width if not text else min(box.width * 0.4, box.height * ratio)
        img_box = pymupdf.Rect(box.x0, box.y0, box.x0 + img_w, box.y1)
        page.insert_image(img_box * page.derotation_matrix, stream=png, keep_proportion=True, rotate=-rotation)
        text_box = pymupdf.Rect(img_box.x1 + pad, box.y0, box.x1, box.y1)
    if text and text_box.width > 8:
        font_path = unicode_font_path()
        size_pt = 11.0
        while size_pt >= 4:
            rc = page.insert_textbox(
                text_box * page.derotation_matrix,
                text,
                fontsize=size_pt,
                fontname="apt-uni" if font_path else "helv",
                fontfile=font_path,
                rotate=rotation,
            )
            if rc >= 0:
                break
            size_pt -= 0.5
    page.set_rotation(0)
    doc.subset_fonts()
    doc.save(out, garbage=4, deflate=True)
    doc.close()


def normalise_encryption(src: Path, dst: Path, password: str) -> None:
    """Rewrite an encrypted PDF with the same encryption via qpdf.

    MuPDF (and some other writers) store ``/Encrypt`` as a direct trailer
    dictionary, which pyHanko's incremental writer cannot carry forward. qpdf
    writes it as an indirect object and copies the original keys, so the
    owner password and permissions survive. Only safe before the first
    signature: a full rewrite would break existing ones.
    """
    import pikepdf

    try:
        with pikepdf.open(src, password=password) as pdf:
            pdf.save(dst, encryption=True)
    except pikepdf.PasswordError as e:
        raise UserError(
            "PDF şifreli — doğru şifreyi girin.",
            "The PDF is password-protected — enter the correct password.",
        ) from e
    except pikepdf.PdfError as e:
        raise UserError("Şifreli PDF işlenemedi.", "Cannot process the encrypted PDF.") from e


def _resolve_page(spec: str, count: int) -> int:
    if spec in ("last", "son"):
        return count - 1
    n = int(spec)
    if not 1 <= n <= count:
        raise UserError(f"Sayfa {n} aralık dışında (1–{count}).", f"Page {n} is out of range (1–{count}).")
    return n - 1


@register
class Sign(Operation):
    name = "sign"
    category = "sign"
    title_tr, title_en = "Dijital İmzala", "Digitally Sign"
    description_tr = "PDF'i .p12/.pfx sertifikanızla PAdES dijital imzayla imzalar (görünür veya görünmez)."
    description_en = "Sign the PDF with your .p12/.pfx certificate as a PAdES digital signature (visible or invisible)."
    Params = SignParams

    def run(self, ctx: Context, params: SignParams) -> None:
        from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
        from pyhanko.sign import fields, signers
        from pyhanko.stamp import StaticStampStyle

        signer, cert = load_pkcs12(ctx.files["certificate"].path, params.certificate_password)
        inp = ctx.inputs[0]
        stamp: Path | None = None
        new_field: Any = None
        with open_pdf(inp.path, inp.password) as doc:
            index = FormIndex(doc)
            existing = index.fields.get(params.field_name)
            if existing:
                page, widget = existing[0]
                if TYPE_NAMES.get(widget.field_type) != "signature":
                    raise UserError(
                        f"'{params.field_name}' adlı alan bir imza alanı değil.",
                        f"The field '{params.field_name}' is not a signature field.",
                    )
                if doc.xref_get_key(widget.xref, "V")[0] != "null":
                    raise UserError(
                        f"'{params.field_name}' alanı zaten imzalı — başka bir alan adı girin.",
                        f"The field '{params.field_name}' is already signed — enter another field name.",
                    )
                # An existing visible field always gets our appearance;
                # otherwise pyHanko would draw its own English default.
                rect = pymupdf.Rect(widget.rect)
                visible = not rect.is_empty and rect.width > 1 and rect.height > 1
                rotation = page.rotation
                size = (rect.width, rect.height)
            else:
                page = doc[_resolve_page(params.page, doc.page_count)]
                rotation = page.rotation
                visible = params.visible
                box = self._box(page, params.rect)
                size = (box.width, box.height)
                new_field = fields.SigFieldSpec(
                    params.field_name,
                    on_page=page.number,
                    box=(box.x0, box.y0, box.x1, box.y1) if visible else None,
                )
            encrypted = bool(doc.is_encrypted or doc.needs_pass or (doc.metadata or {}).get("encryption"))
            signed_before = any(
                TYPE_NAMES.get(w.field_type) == "signature" and doc.xref_get_key(w.xref, "V")[0] != "null"
                for widgets in index.fields.values()
                for _, w in widgets
            )
        if visible:
            when = _dt.datetime.now().astimezone()
            text = render_appearance(
                params.appearance_text,
                {
                    "name": _name_attr(cert.subject, NameOID.COMMON_NAME),
                    "date": when.strftime("%d.%m.%Y %H:%M"),
                    "reason": params.reason.strip(),
                    "location": params.location.strip(),
                },
            )
            image = ctx.files["signature_image"].path if "signature_image" in ctx.files else None
            stamp = ctx.output_dir / ".signature-appearance.pdf"
            build_stamp(stamp, size, rotation, text, image)
        ctx.progress(0.4, "")

        meta = signers.PdfSignatureMetadata(
            field_name=params.field_name,
            reason=params.reason.strip() or None,
            location=params.location.strip() or None,
            contact_info=params.contact.strip() or None,
            md_algorithm="sha256",
            subfilter=fields.SigSeedSubFilter.PADES,
        )
        style = StaticStampStyle.from_pdf_file(str(stamp), border_width=0) if stamp else None
        pdf_signer = signers.PdfSigner(meta, signer, stamp_style=style, new_field_spec=new_field)
        source = inp.path
        if encrypted and not signed_before:
            source = ctx.output_dir / ".normalised.pdf"
            normalise_encryption(inp.path, source, inp.password)
        out = ctx.output(f"{inp.stem}_imzali.pdf")
        try:
            with source.open("rb") as src, out.open("wb") as dst:
                writer = IncrementalPdfFileWriter(src, strict=False)
                if encrypted:
                    writer.encrypt(inp.password)  # type: ignore[no-untyped-call]
                pdf_signer.sign_pdf(writer, output=dst)
        except UserError:
            raise
        except Exception as e:
            out.unlink(missing_ok=True)
            raise UserError(
                "PDF imzalanamadı. Belge değişikliğe kapalı (onaylı/kilitli) veya bozuk olabilir.",
                "Could not sign the PDF. It may be locked against changes (certified) or damaged.",
            ) from e
        finally:
            if stamp:
                stamp.unlink(missing_ok=True)
            if source != inp.path:
                source.unlink(missing_ok=True)

    @staticmethod
    def _box(page: Any, rect: list[float] | None) -> pymupdf.Rect:
        """The new field's box in PDF user space, checked against the page."""
        to_pdf = ~page.transformation_matrix
        area = (pymupdf.Rect(0, 0, page.cropbox.width, page.cropbox.height) * to_pdf).normalize()
        if rect is None:
            # Bottom-right of the page as the reader sees it.
            vis = page.rect
            w, h = min(200.0, vis.width - 72), min(70.0, vis.height - 72)
            corner = pymupdf.Rect(vis.x1 - 36 - w, vis.y1 - 36 - h, vis.x1 - 36, vis.y1 - 36)
            return (corner * page.derotation_matrix * to_pdf).normalize()
        box = pymupdf.Rect(rect).normalize()
        if box.width < 10 or box.height < 10 or not within(area, box):
            raise UserError(
                "İmza konumu sayfanın dışında veya çok küçük.",
                "The signature position is outside the page or too small.",
            )
        return box


# -- verification ----------------------------------------------------------------
def _subject(cert: Any) -> dict[str, str]:
    """asn1crypto certificate → the few subject fields people recognise."""
    if cert is None:
        return {"common_name": "", "organisation": "", "email": ""}
    native = cert.subject.native
    return {
        "common_name": str(native.get("common_name", "")),
        "organisation": str(native.get("organization_name", "")),
        "email": str(native.get("email_address", "")),
    }


def _trust_reason(status: Any, cert: Any) -> dict[str, str] | None:
    if status.trusted:
        return None
    if getattr(status, "revoked", False):
        return {"tr": "Sertifika iptal edilmiş.", "en": "The certificate has been revoked."}
    if cert is not None and cert.subject == cert.issuer:
        return {
            "tr": "Sertifika kendinden imzalı; güvenilir bir sertifika makamına bağlı değil.",
            "en": "The certificate is self-signed; it does not chain to a trusted certificate authority.",
        }
    return {
        "tr": "Sertifika zinciri sistemdeki güvenilir köklere bağlanamadı (çevrimdışı doğrulama).",
        "en": "The certificate chain does not reach a trusted root on this system (offline validation).",
    }


def verify_one(sig: Any, vc: Any) -> dict[str, Any]:
    from pyhanko.pdf_utils.misc import PdfError
    from pyhanko.sign.general import CMSExtractionError, CMSStructuralError
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko.sign.validation.errors import SignatureValidationError

    cert = sig.signer_cert
    entry: dict[str, Any] = {"field": str(sig.field_name), "signer": _subject(cert)}
    try:
        with _quiet_pyhanko():
            status = validate_pdf_signature(sig, vc)
    except (SignatureValidationError, CMSExtractionError, CMSStructuralError, PdfError, ValueError, KeyError) as e:
        return entry | {
            "intact": False,
            "valid": False,
            "trusted": False,
            "error": {
                "tr": "İmza doğrulanamadı (bozuk imza verisi).",
                "en": f"Signature cannot be validated: {e}"[:300],
            },
        }
    when = status.signer_reported_dt
    coverage = status.coverage.name if status.coverage is not None else None
    level = status.modification_level.name if status.modification_level is not None else None
    docmdp = sig.docmdp_level
    entry |= {
        "signing_time": when.isoformat() if when else None,
        "timestamped": status.timestamp_validity is not None,
        "intact": bool(status.intact),
        "valid": bool(status.valid),
        "trusted": bool(status.trusted),
        "trust_problem": _trust_reason(status, cert),
        "coverage": coverage,
        "covers_whole_document": coverage == "ENTIRE_FILE",
        "modified_after_signing": coverage != "ENTIRE_FILE",
        "modification_level": level,
        "docmdp": docmdp.name if docmdp is not None else None,
        "docmdp_ok": status.docmdp_ok,
        "summary": status.summary(),
    }
    return entry


@register
class VerifySignatures(Operation):
    name = "verify_signatures"
    category = "sign"
    title_tr, title_en = "İmzaları Doğrula", "Verify Signatures"
    description_tr = "PDF'teki dijital imzaları denetler: bütünlük, geçerlilik, güven ve imzadan sonraki değişiklikler."
    description_en = "Check the PDF's digital signatures: integrity, validity, trust and changes made after signing."
    returns_data = True

    def run(self, ctx: Context, params: object) -> None:
        from pyhanko.pdf_utils.crypt import AuthStatus
        from pyhanko.pdf_utils.misc import PdfError
        from pyhanko.pdf_utils.reader import PdfFileReader
        from pyhanko_certvalidator import ValidationContext

        inp = ctx.inputs[0]
        with open_pdf(inp.path, inp.password):
            pass  # same validity / password errors as every other tool
        results: list[dict[str, Any]] = []
        with inp.path.open("rb") as f:
            try:
                reader = PdfFileReader(f, strict=False)
                if reader.encrypted and reader.decrypt(inp.password).status == AuthStatus.FAILED:
                    raise UserError(
                        "PDF şifreli — doğru şifreyi girin.",
                        "The PDF is password-protected — enter the correct password.",
                    )
                sigs = reader.embedded_signatures
            except PdfError as e:
                raise UserError("PDF'in imza yapısı okunamadı.", "Cannot read the PDF's signature structure.") from e
            # No fetching: the app is offline-first and verification must not
            # leak which documents are being checked.
            vc = ValidationContext(allow_fetching=False)
            for k, sig in enumerate(sigs[:MAX_SIGNATURES]):
                results.append(verify_one(sig, vc))
                ctx.progress((k + 1) / max(1, len(sigs)), "")
        ctx.data = {
            "signatures": results,
            "count": len(results),
            "all_valid": bool(results) and all(r["intact"] and r["valid"] for r in results),
        }
