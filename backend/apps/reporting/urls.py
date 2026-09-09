from django.urls import path

from .views import DashboardView, ExportCsvView, ReportPdfView, ReportView

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="reporting-dashboard"),
    path("report/", ReportView.as_view(), name="reporting-report"),
    path("report.pdf", ReportPdfView.as_view(), name="reporting-report-pdf"),
    path("export.csv", ExportCsvView.as_view(), name="reporting-export-csv"),
]
