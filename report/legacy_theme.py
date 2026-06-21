"""Shared theme colors for legacy PPTX/PDF reports."""
from pptx.dml.color import RGBColor

try:
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

class ReportTheme:
    """报告主题颜色和字体"""

    # 字体配置 - 统一专业字体
    FONT_TITLE_CN = "Microsoft YaHei"      # 中文标题
    FONT_BODY_CN = "Microsoft YaHei"       # 中文字体
    FONT_TITLE_EN = "Times New Roman"       # 英文标题
    FONT_BODY_EN = "Times New Roman"        # 英文字体
    FONT_MONO = "Consolas"                  # 等宽字体 (用于数据/代码)

    # 主色调
    PRIMARY = RGBColor(0x2C, 0x3E, 0x50)      # 深蓝灰
    SECONDARY = RGBColor(0x34, 0x98, 0xDB)     # 蓝色
    ACCENT = RGBColor(0xE7, 0x4C, 0x3C)       # 红色
    SUCCESS = RGBColor(0x27, 0xAE, 0x60)       # 绿色
    WARNING = RGBColor(0xF3, 0x9C, 0x12)       # 橙色
    INFO = RGBColor(0x5D, 0xAD, 0xE2)          # 浅蓝

    # 中性色
    TEXT = RGBColor(0x2C, 0x3E, 0x50)          # 文本色
    TEXT_LIGHT = RGBColor(0x7F, 0x8C, 0x8D)    # 浅文本
    BACKGROUND = RGBColor(0xF8, 0xF9, 0xFA)    # 背景色
    WHITE = RGBColor(0xFF, 0xFF, 0xFF)         # 白色
    BORDER = RGBColor(0xDE, 0xE2, 0xE6)        # 边框色

    # 严重程度颜色
    CRITICAL = RGBColor(0xC0, 0x39, 0x2B)      # 深红
    WARNING_COLOR = RGBColor(0xF3, 0x9C, 0x12) # 橙
    INFO_COLOR = RGBColor(0x34, 0x98, 0xDB)    # 蓝

    # ReportLab颜色 (PDF用) - 只在reportlab可用时定义
    if REPORTLAB_AVAILABLE:
        RL_CRITICAL = colors.HexColor('#C0392B')
        RL_WARNING = colors.HexColor('#F39C12')
        RL_INFO = colors.HexColor('#3498DB')
        RL_SUCCESS = colors.HexColor('#27AE60')
        RL_PRIMARY = colors.HexColor('#2C3E50')
