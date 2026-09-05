from app.main import create_app
from app.tools.pdf_export import markdown_report_to_pdf


def test_markdown_report_to_pdf_returns_valid_document() -> None:
    document = markdown_report_to_pdf("# Analysis Report\n\n- Base shear: 120 kN\n- Drift: 8 mm")

    assert document.startswith(b"%PDF-1.4")
    assert b"Analysis Report" in document
    assert document.rstrip().endswith(b"%%EOF")


def test_markdown_report_to_pdf_paginates_long_reports() -> None:
    document = markdown_report_to_pdf("\n".join(f"Result line {index}" for index in range(150)))

    assert b"/Count 3" in document
    assert document.count(b"/Type /Page ") == 3


def test_export_pdf_route_downloads_pdf() -> None:
    client = create_app().test_client()
    response = client.post("/api/export/pdf", json={"report_markdown": "# Frame Report\n\nSafe output."})

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF-1.4")
    assert "analysis_report.pdf" in response.headers["Content-Disposition"]


def test_export_pdf_route_rejects_missing_report() -> None:
    client = create_app().test_client()
    response = client.post("/api/export/pdf", json={})

    assert response.status_code == 400
    assert response.get_json()["status"] == "error"
