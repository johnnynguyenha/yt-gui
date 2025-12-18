import sys, os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QLineEdit, QPushButton, QProgressBar, QTextEdit, QLabel, QRadioButton, QHBoxLayout, QFileDialog
)
from PySide6.QtCore import QThread, Signal, Qt
from yt_dlp import YoutubeDL

class YTDLPLogger:
    def __init__(self, log_signal):
        self.log_signal = log_signal

    def debug(self, msg):
        # filter useless lines
        if msg.startswith('[debug]'):
            return
        self.log_signal.emit(msg)

    def info(self, msg):
        self.log_signal.emit(msg)

    def warning(self, msg):
        self.log_signal.emit(f"Warning: {msg}")

    def error(self, msg):
        self.log_signal.emit(f"Error: {msg}")

class DownloadWorker(QThread):
    progress = Signal(int)
    log = Signal(str)
    finished = Signal()

    def __init__(self, url, is_mp3, output_dir):
        super().__init__()
        self.url = url
        self.is_mp3 = is_mp3
        self.output_dir = output_dir

    def run(self):
        def hook(d):
            if d['status'] == 'downloading':
                # try multiple ways to get progress
                if 'downloaded_bytes' in d and 'total_bytes' in d:
                    percent = (d['downloaded_bytes'] / d['total_bytes']) * 100
                    self.progress.emit(int(percent))
                elif 'downloaded_bytes' in d and 'total_bytes_estimate' in d:
                    percent = (d['downloaded_bytes'] / d['total_bytes_estimate']) * 100
                    self.progress.emit(int(percent))
                elif '_percent_str' in d:
                    percent_str = d['_percent_str'].replace('%', '').strip()
                    try:
                        self.progress.emit(int(float(percent_str)))
                    except (ValueError, AttributeError):
                        pass
            
            elif d['status'] == 'finished':
                self.progress.emit(100)
                self.log.emit("Download finished")

        ydl_opts = {
            'outtmpl': os.path.join(self.output_dir, '%(title)s.%(ext)s'),
            'progress_hooks': [hook],
            'logger': YTDLPLogger(self.log),   
            'verbose': True,                  # enable console output
        }

        if self.is_mp3:
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
            })
        else: # automatically do h.264 (premiere pro compatbile)
            self.log.emit("Mode: MP4 (H.264 / AVC)")
            ydl_opts.update({
                'format': 'bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best',
                'merge_output_format': 'mp4',
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor', # requires ffmpeg
                    'preferedformat': 'mp4',
                }],
            })

        try:
            with YoutubeDL(ydl_opts) as ydl:
                self.log.emit("Starting download...")
                ydl.download([self.url])

        except Exception as e:
            self.log.emit(f"Exception: {e}")

        self.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("yt-dlp GUI by Johnny Nguyen")
        self.setMinimumSize(500, 300)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter Youtube URL")

        self.output_label = QLabel("Output folder:")
        self.output_path = QLineEdit()
        self.output_path.setReadOnly(True)

        self.browse_button = QPushButton("Browse...")

        self.dl_button = QPushButton("Download")
        self.progress_bar = QProgressBar()
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.mp4_radio = QRadioButton("MP4 (Video)")
        self.mp3_radio = QRadioButton("MP3 (Audio only)")
        self.mp4_radio.setChecked(True)  # default  

        radio_layout = QHBoxLayout()
        radio_layout.addWidget(self.mp4_radio)
        radio_layout.addWidget(self.mp3_radio)

        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_path)
        output_layout.addWidget(self.browse_button)

        layout = QVBoxLayout()
        layout.addWidget(self.url_input)
        layout.addWidget(self.output_label)
        layout.addLayout(output_layout)
        layout.addWidget(self.dl_button)
        layout.addLayout(radio_layout)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.log_box)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.dl_button.clicked.connect(self.start_download)
        self.browse_button.clicked.connect(self.choose_output_dir)

        self.log_box.textChanged.connect(
            lambda: self.log_box.verticalScrollBar().setValue(
                self.log_box.verticalScrollBar().maximum()
            )
        )

    def start_download(self):
        url = self.url_input.text().strip()
        if not url:
            self.log_box.append("Please enter a URL")
            return
        
        output_dir = self.output_path.text().strip()
        if not output_dir:
            self.log_box.append("Please select an output folder")
            return

        is_mp3 = self.mp3_radio.isChecked()
    
        self.progress_bar.setValue(0)
        self.log_box.clear()

        self.worker = DownloadWorker(url, is_mp3, output_dir)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.log.connect(self.log_box.append)
        self.worker.finished.connect(self.download_finished)

        self.dl_button.setEnabled(False)
        self.worker.start()

    def download_finished(self):
        self.dl_button.setEnabled(True)
        self.log_box.append("Ready")

    def choose_output_dir(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder",
            "",
            QFileDialog.ShowDirsOnly
        )
        if folder:
            self.output_path.setText(folder)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())