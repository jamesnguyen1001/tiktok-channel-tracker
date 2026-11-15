DARK_THEME_QSS = """
/* TikTok Growth Tracker - Dark Glassmorphism Modern Theme */

QMainWindow, QDialog, QWidget {
    background-color: #0F172A;
    color: #F8FAFC;
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 13px;
}

/* KPI Cards */
QFrame#kpiCard {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 10px;
}
QFrame#kpiCard:hover {
    border: 1px solid #00F2FE;
}

QLabel#kpiTitle {
    color: #94A3B8;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
}

QLabel#kpiValue {
    color: #FFFFFF;
    font-size: 20px;
    font-weight: 800;
}

QLabel#kpiGrowthPos {
    color: #10B981;
    font-size: 12px;
    font-weight: 700;
}

QLabel#kpiGrowthNeg {
    color: #EF4444;
    font-size: 12px;
    font-weight: 700;
}

/* Buttons */
QPushButton {
    background-color: #1E293B;
    color: #F8FAFC;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 600;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #334155;
    border-color: #475569;
}
QPushButton:pressed {
    background-color: #0F172A;
}
QPushButton:disabled {
    background-color: #0B1120;
    color: #475569;
    border-color: #1E293B;
}

/* Primary Action Button (Cyan / TikTok style) */
QPushButton#btnPrimary {
    background-color: #0284C7;
    color: #FFFFFF;
    border: none;
    font-weight: 700;
}
QPushButton#btnPrimary:hover {
    background-color: #0369A1;
}

/* Success Action Button (Green) */
QPushButton#btnSuccess {
    background-color: #059669;
    color: #FFFFFF;
    border: none;
    font-weight: 700;
}
QPushButton#btnSuccess:hover {
    background-color: #047857;
}

/* Danger Action Button (Red) */
QPushButton#btnDanger {
    background-color: #DC2626;
    color: #FFFFFF;
    border: none;
    font-weight: 700;
}
QPushButton#btnDanger:hover {
    background-color: #B91C1C;
}

/* Main Data Table */
QTableWidget {
    background-color: #111827;
    alternate-background-color: #161F30;
    border: 1px solid #1E293B;
    border-radius: 8px;
    gridline-color: #1E293B;
    color: #E2E8F0;
    selection-background-color: #1E3A8A;
    selection-color: #FFFFFF;
}

QHeaderView::section {
    background-color: #1E293B;
    color: #94A3B8;
    font-weight: 700;
    font-size: 11px;
    padding: 8px 6px;
    border: none;
    border-right: 1px solid #0F172A;
    border-bottom: 2px solid #334155;
}

QHeaderView::section:hover {
    background-color: #334155;
    color: #FFFFFF;
}

/* Inputs & Combos */
QLineEdit, QComboBox, QPlainTextEdit, QSpinBox, QDoubleSpinBox {
    background-color: #1E293B;
    color: #F8FAFC;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #0284C7;
}

QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #38BDF8;
}

QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}
QComboBox QAbstractItemView {
    background-color: #1E293B;
    color: #F8FAFC;
    border: 1px solid #334155;
    selection-background-color: #0284C7;
}

/* Progress Bar */
QProgressBar {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 6px;
    text-align: center;
    color: #FFFFFF;
    font-weight: 700;
    height: 18px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #06B6D4, stop:1 #10B981);
    border-radius: 5px;
}

/* Scrollbars */
QScrollBar:vertical {
    background: #0F172A;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #334155;
    min-height: 20px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #475569;
}
QScrollBar:horizontal {
    background: #0F172A;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #334155;
    min-width: 20px;
    border-radius: 5px;
}

/* GroupBox */
QGroupBox {
    border: 1px solid #334155;
    border-radius: 8px;
    margin-top: 14px;
    font-weight: 700;
    color: #38BDF8;
    padding-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 4px;
}

/* Context Menu */
QMenu {
    background-color: #1E293B;
    color: #F8FAFC;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 20px 6px 12px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #0284C7;
    color: #FFFFFF;
}
QMenu::separator {
    height: 1px;
    background: #334155;
    margin: 4px 0;
}
"""
