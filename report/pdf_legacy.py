"""Legacy full-pipeline PDF report generator."""
from datetime import datetime
from typing import List

from config_system import LayoutReviewConfig
from report.legacy_theme import REPORTLAB_AVAILABLE, ReportTheme
from review_engine import (
    ProfessionalLayoutReviewEngine,
    ReviewSummary,
    Severity,
    Violation,
)

if REPORTLAB_AVAILABLE:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

class PDFReportGenerator:
    """PDF格式报告生成器"""

    def __init__(self):
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab is required for PDF export")
        self.theme = ReportTheme()
        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _setup_styles(self):
        """设置PDF样式"""
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=self.theme.RL_PRIMARY,
            spaceAfter=30
        )

        self.heading_style = ParagraphStyle(
            'CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=self.theme.RL_PRIMARY,
            spaceAfter=12
        )

        self.subheading_style = ParagraphStyle(
            'CustomSubHeading',
            parent=self.styles['Heading3'],
            fontSize=13,
            textColor=self.theme.RL_PRIMARY,
            spaceAfter=10
        )

        self.normal_style = ParagraphStyle(
            'CustomNormal',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=6
        )

    def create_report(self, engine: ProfessionalLayoutReviewEngine,
                      title: str = "Layout Review Report") -> List:
        """创建PDF报告内容"""
        story = []
        summary = engine._generate_summary()

        # 封面
        story.extend(self._create_cover(title, engine.config))
        story.append(PageBreak())

        # 目录
        story.extend(self._create_toc())
        story.append(PageBreak())

        # Executive Summary
        story.extend(self._create_summary(summary, engine))
        story.append(PageBreak())

        # Net Statistics
        story.extend(self._create_net_statistics(engine))
        story.append(PageBreak())

        # Violations
        if summary.total_violations > 0:
            story.extend(self._create_violations_section(engine))
            story.append(PageBreak())

        # Matching Analysis
        if engine.matching_results:
            story.extend(self._create_matching_section(engine))
            story.append(PageBreak())

        # Recommendations
        story.extend(self._create_recommendations(engine))

        return story

    def _create_cover(self, title: str, config: LayoutReviewConfig) -> List:
        """创建封面"""
        story = []

        story.append(Spacer(1, 2*inch))
        story.append(Paragraph(title, self.title_style))
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph(f"Technology: {config.tech_config.name}", self.heading_style))
        story.append(Paragraph(f"Process Node: {config.tech_config.node}", self.normal_style))
        story.append(Spacer(1, 1*inch))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", self.normal_style))
        story.append(Paragraph("Professional Layout Review Engine v1.0", self.normal_style))

        return story

    def _create_toc(self) -> List:
        """创建目录"""
        story = []
        story.append(Paragraph("Table of Contents", self.heading_style))
        story.append(Spacer(1, 0.2*inch))

        sections = [
            "1. Executive Summary",
            "2. Net Statistics Overview",
            "3. Violation Analysis",
            "4. Matching Analysis",
            "5. Recommendations"
        ]

        for section in sections:
            story.append(Paragraph(section, self.normal_style))

        return story

    def _create_summary(self, summary: ReviewSummary, engine: ProfessionalLayoutReviewEngine) -> List:
        """创建Executive Summary"""
        story = []
        story.append(Paragraph("1. Executive Summary", self.heading_style))
        story.append(Spacer(1, 0.2*inch))

        # 统计表格
        data = [
            ['Metric', 'Value'],
            ['Total Nets', str(summary.total_nets)],
            ['Critical Issues', str(summary.critical_count)],
            ['Warnings', str(summary.warning_count)],
            ['Info Messages', str(summary.info_count)],
            ['Matching Pairs', str(summary.matching_pairs_analyzed)],
        ]

        table = Table(data, colWidths=[3*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.theme.RL_PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))

        story.append(table)
        story.append(Spacer(1, 0.3*inch))

        # RC Summary
        story.append(Paragraph("RC Analysis Summary", self.subheading_style))
        rc_data = [
            ['Parameter', 'Value'],
            ['Resistance Range', f"{summary.total_resistance_range[0]:.1f} - {summary.total_resistance_range[1]:.1f} Ω"],
            ['Average Resistance', f"{summary.avg_resistance:.1f} Ω"],
            ['Capacitance Range', f"{summary.total_capacitance_range[0]:.1f} - {summary.total_capacitance_range[1]:.1f} fF"],
            ['Average Capacitance', f"{summary.avg_capacitance:.1f} fF"],
        ]

        rc_table = Table(rc_data, colWidths=[3*inch, 2.5*inch])
        rc_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.theme.RL_PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))

        story.append(rc_table)

        return story

    def _create_net_statistics(self, engine: ProfessionalLayoutReviewEngine) -> List:
        """创建Net统计"""
        story = []
        story.append(Paragraph("2. Net Statistics Overview", self.heading_style))
        story.append(Spacer(1, 0.2*inch))

        table_data = engine.get_net_info_table()
        if not table_data:
            return story

        # 表头
        headers = ['Net Name', 'R (Ω)', 'C (fF)', 'Length', 'Vias', 'Violations']
        data = [headers]

        # 数据行 (最多20个)
        for row in table_data[:20]:
            data.append([
                row['Net Name'],
                f"{row['Total R (Ω)']:.2f}",
                f"{row['Total C (fF)']:.1f}",
                f"{row['Length (μm)']:.1f}",
                str(row['Via Count']),
                str(row['Violations'])
            ])

        table = Table(data, colWidths=[2.5*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.7*inch, 0.9*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.theme.RL_PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))

        story.append(table)

        return story

    def _create_violations_section(self, engine: ProfessionalLayoutReviewEngine) -> List:
        """创建违规分析"""
        story = []
        story.append(Paragraph("3. Violation Analysis", self.heading_style))
        story.append(Spacer(1, 0.2*inch))

        # 按严重程度分组
        critical = [v for v in engine.violations if v.severity == Severity.CRITICAL]
        warnings = [v for v in engine.violations if v.severity == Severity.WARNING]

        if critical:
            story.append(Paragraph("Critical Issues", self.subheading_style))
            for v in critical[:5]:  # 最多5个
                story.extend(self._create_violation_item(v))
            story.append(Spacer(1, 0.2*inch))

        if warnings:
            story.append(Paragraph("Warnings", self.subheading_style))
            for v in warnings[:5]:
                story.extend(self._create_violation_item(v))

        return story

    def _create_violation_item(self, v: Violation) -> List:
        """创建单个违规项"""
        story = []

        color = self.theme.RL_CRITICAL if v.severity == Severity.CRITICAL else \
                self.theme.RL_WARNING if v.severity == Severity.WARNING else self.theme.RL_INFO

        story.append(Paragraph(
            f"<font color='#{color.hexval()[2:8]}'><b>[{v.rule_id}]</b></font> {v.rule_name}",
            self.normal_style
        ))
        story.append(Paragraph(f"Net: <b>{v.net_name}</b>", self.normal_style))
        story.append(Paragraph(v.message, self.normal_style))
        if v.suggestion:
            story.append(Paragraph(f"<i>Suggestion: {v.suggestion}</i>", self.normal_style))
        story.append(Spacer(1, 0.1*inch))

        return story

    def _create_matching_section(self, engine: ProfessionalLayoutReviewEngine) -> List:
        """创建匹配分析"""
        story = []
        story.append(Paragraph("4. Matching Analysis", self.heading_style))
        story.append(Spacer(1, 0.2*inch))

        for match in engine.matching_results[:10]:  # 最多10个
            score_color = self.theme.RL_SUCCESS if match.match_score >= 80 else \
                         self.theme.RL_WARNING if match.match_score >= 60 else self.theme.RL_CRITICAL

            story.append(Paragraph(
                f"<b>{match.net1} ↔ {match.net2}</b> " +
                f"(<font color='#{score_color.hexval()[2:8]}'>Score: {match.match_score:.1f}</font>)",
                self.subheading_style
            ))

            data = [
                ['Metric', 'Value'],
                ['Length Ratio', f"{match.length_ratio:.3f}"],
                ['Resistance Ratio', f"{match.resistance_ratio:.3f}"],
                ['Via Count Diff', str(match.via_count_diff)],
            ]

            table = Table(data, colWidths=[2*inch, 1.5*inch])
            table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ]))
            story.append(table)

            if match.issues:
                story.append(Paragraph("Issues:", self.normal_style))
                for issue in match.issues[:3]:
                    story.append(Paragraph(f"- {issue}", self.normal_style))

            story.append(Spacer(1, 0.2*inch))

        return story

    def _create_recommendations(self, engine: ProfessionalLayoutReviewEngine) -> List:
        """创建建议"""
        story = []
        story.append(Paragraph("5. Recommendations", self.heading_style))
        story.append(Spacer(1, 0.2*inch))

        suggestions = set()
        for v in engine.violations:
            if v.suggestion:
                suggestions.add(v.suggestion)

        for sug in sorted(suggestions)[:15]:
            story.append(Paragraph(f"• {sug}", self.normal_style))

        return story

    def save(self, story: List, filepath: str):
        """保存PDF"""
        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=1*inch,
            bottomMargin=1*inch
        )
        doc.build(story)
        print(f"✓ PDF report saved: {filepath}")
