"""Call-log workflow plugin (v1 "çağrı kaydı" batch tools, ported to v2).

Turns 360 call-centre call-log PDFs — and other same-format table PDFs —
into merged Excel workbooks, removes duplicates, filters, and distributes the
rows to teams. Every operation is stateless: PDFs or a workbook from the
previous step go in, a new file (plus ``ctx.data`` stats) comes out.
"""

from . import ops as ops
