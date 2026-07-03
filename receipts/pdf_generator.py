"""Generate receipt PDF menggunakan reportlab."""
import io
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A7
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

WIDTH, HEIGHT = A7  # 74mm x 105mm — thermal receipt


def _format_idr(amount) -> str:
    """Format ke string Rupiah."""
    if amount is None or amount == '':
        return 'Rp 0'
    return f'Rp {Decimal(amount):,.0f}'


def _format_duration(minutes):
    """Format menit ke jam:menit."""
    if minutes is None:
        return '-'
    total_min = int(minutes)
    h = total_min // 60
    m = total_min % 60
    if h > 0:
        return f'{h}j {m}m'
    return f'{m}m'


def generate_receipt_pdf(session, receipt) -> bytes:
    """
    Generate PDF receipt untuk session yang sudah paid.

    Args:
        session: PlaySession instance dengan payment terkait.
        receipt: Receipt instance.

    Returns:
        bytes: PDF content.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A7,
        leftMargin=4 * mm,
        rightMargin=4 * mm,
        topMargin=4 * mm,
        bottomMargin=4 * mm,
    )

    elements = []
    styles = getSampleStyleSheet()

    # Custom styles
    center_style = ParagraphStyle(
        'CenterStyle', parent=styles['Normal'],
        alignment=1, fontSize=8, leading=10,
    )
    left_style = ParagraphStyle(
        'LeftStyle', parent=styles['Normal'],
        fontSize=7, leading=9,
    )
    bold_style = ParagraphStyle(
        'BoldStyle', parent=left_style, fontName='Helvetica-Bold',
    )

    # Header
    outlet_name = session.outlet.name
    elements.append(Paragraph(f'<b>{outlet_name}</b>', center_style))
    elements.append(Paragraph('Smart Billiard POS', center_style))
    elements.append(Spacer(1, 2 * mm))

    # Invoice
    elements.append(Paragraph(f'Invoice: {receipt.invoice_number}', bold_style))
    printed_at = timezone.localtime(receipt.printed_at)
    elements.append(Paragraph(f'Tgl: {printed_at.strftime("%d/%m/%Y %H:%M")}', left_style))
    elements.append(Spacer(1, 1 * mm))

    # Divider
    elements.append(Paragraph('=' * 32, center_style))

    # Customer
    elements.append(Paragraph(f'Pelanggan: {session.customer_name}', left_style))
    if session.customer_phone:
        elements.append(Paragraph(f'Telp: {session.customer_phone}', left_style))

    # Session info
    started = timezone.localtime(session.started_at)
    ended = timezone.localtime(session.ended_at) if session.ended_at else '-'
    elements.append(Paragraph(f'Mulai: {started.strftime("%d/%m %H:%M")}', left_style))
    elements.append(Paragraph(f'Selesai: {ended.strftime("%d/%m %H:%M")}', left_style))
    elements.append(Spacer(1, 1 * mm))

    # Table logs
    elements.append(Paragraph('=' * 32, center_style))
    elements.append(Paragraph('<b>Rincian Meja</b>', bold_style))

    from sessions.models import SessionTableLog
    logs = SessionTableLog.objects.filter(session_id=session.id).order_by('started_at').select_related('table')

    table_data = [
        ['Meja', 'Durasi', 'Tarif/mnt', 'Jumlah'],
    ]
    for log in logs:
        table_data.append([
            log.table.name,
            _format_duration(log.duration_minutes),
            _format_idr(log.rate_source_snapshot.get('price_per_minute', 0)
                        if isinstance(log.rate_source_snapshot, dict) else Decimal('0')),
            _format_idr(log.amount),
        ])

    tbl = Table(table_data, colWidths=[17 * mm, 14 * mm, 17 * mm, 18 * mm])
    tbl.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 6),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 1 * mm))

    # Summary
    elements.append(Paragraph('=' * 32, center_style))
    elements.append(Paragraph(f'Subtotal: {_format_idr(session.subtotal)}', left_style))
    if session.additional_fee_total:
        elements.append(Paragraph(f'Biaya Tambahan: {_format_idr(session.additional_fee_total)}', left_style))
    elements.append(Paragraph(f'<b>Total: {_format_idr(session.total_amount)}</b>', bold_style))
    elements.append(Spacer(1, 1 * mm))

    # Payment
    payment = session.payments.filter(status='paid').first()
    if payment:
        elements.append(Paragraph(f'Metode: {payment.get_method_display()}', left_style))
    elements.append(Paragraph(f'Dicetak oleh: {receipt.printed_by.username}', left_style))
    elements.append(Spacer(1, 2 * mm))

    # Footer
    elements.append(Paragraph('=' * 32, center_style))
    elements.append(Paragraph('Terima kasih telah bermain!', center_style))

    doc.build(elements)
    return buf.getvalue()