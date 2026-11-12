"""Alibaba Product Auto Uploader 桌面启动入口。"""
import logging
import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow, APP_VERSION


def main() -> int:
    """启动桌面界面；不初始化任何客户端自动化。"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = QApplication(sys.argv)
    app.setApplicationName("Alibaba Product Auto Uploader")
    app.setOrganizationName("AlibabaAutoUploader")
    app.setApplicationVersion(APP_VERSION)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
