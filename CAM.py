import sys
import os
import cv2
import uuid
from datetime import datetime
import numpy as np

# PyQt5 imports
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QComboBox, QSpinBox, QCheckBox, 
    QListWidget, QListWidgetItem, QListView, QFileDialog, QStackedWidget, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import QImage, QPixmap, QPainter, QBrush, QIcon, QFont

APP_NAME = "CAMpy"
DEFAULT_DIR = os.path.join(os.path.expanduser("~"), "CAMpyRoll")

class ScaledLabel(QLabel):
    """A QLabel that automatically scales its pixmap to fit its size while maintaining aspect ratio."""
    def __init__(self):
        super().__init__()
        self.pix = None
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(400, 300)
        self.setAlignment(Qt.AlignCenter)

    def setPixmap(self, pix):
        self.pix = pix
        self.update()

    def paintEvent(self, event):
        if self.pix and not self.pix.isNull():
            painter = QPainter(self)
            scaled_pix = self.pix.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = (self.width() - scaled_pix.width()) // 2
            y = (self.height() - scaled_pix.height()) // 2
            painter.drawPixmap(x, y, scaled_pix)
        else:
            super().paintEvent(event)


class ThumbnailLoader(QThread):
    """Background thread to load thumbnails without freezing the UI."""
    thumbnail_loaded = pyqtSignal(str, QImage)
    finished = pyqtSignal()

    def __init__(self, directory):
        super().__init__()
        self.directory = directory
        self._run_flag = True

    def run(self):
        valid_exts = {'.png', '.jpg', '.jpeg'}
        if os.path.exists(self.directory):
            files = sorted([f for f in os.listdir(self.directory) if os.path.splitext(f)[1].lower() in valid_exts])
            for f in files:
                if not self._run_flag: break
                path = os.path.join(self.directory, f)
                
                # Load small version for memory efficiency
                img = QImage(path)
                if not img.isNull():
                    # Scale QImage instead of QPixmap in the background thread
                    scaled_img = img.scaled(120, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.thumbnail_loaded.emit(path, scaled_img)
        self.finished.emit()

    def stop(self):
        self._run_flag = False
        self.wait()


class CameraThread(QThread):
    """Handles OpenCV video capture and batch saving on a separate thread."""
    change_pixmap_signal = pyqtSignal(QImage)
    image_saved_signal = pyqtSignal(str)
    capture_finished_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._run_flag = True
        self.cam_index = 0
        self.cam_change_requested = False
        self.cap = cv2.VideoCapture(self.cam_index)
        self.capture_queue = []
        self.current_format = "1:1"
        self.res_change_requested = False
        self.req_w = 640
        self.req_h = 480

    def crop_image(self, img, ratio_str):
        h, w = img.shape[:2]
        target_ratio = 1.0
        if ratio_str == "4:3":
            target_ratio = 4.0 / 3.0
        elif ratio_str == "16:9":
            target_ratio = 16.0 / 9.0

        current_ratio = w / h
        if current_ratio > target_ratio:
            new_w = int(h * target_ratio)
            start_x = (w - new_w) // 2
            return img[:, start_x:start_x+new_w]
        elif current_ratio < target_ratio:
            new_h = int(w / target_ratio)
            start_y = (h - new_h) // 2
            return img[start_y:start_y+new_h, :]
        return img

    def run(self):
        while self._run_flag:
            if self.cam_change_requested:
                if self.cap.isOpened():
                    self.cap.release()
                self.cap = cv2.VideoCapture(self.cam_index)
                self.cam_change_requested = False

            if self.res_change_requested:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.req_w)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.req_h)
                self.res_change_requested = False

            ret, cv_img = self.cap.read()
            if ret:
                cropped = self.crop_image(cv_img, self.current_format)
                
                # Check if we need to take pictures
                if self.capture_queue:
                    filename = self.capture_queue.pop(0)
                    cv2.imwrite(filename, cropped)
                    self.image_saved_signal.emit(filename)
                    if not self.capture_queue:
                        self.capture_finished_signal.emit()

                # Convert for display
                rgb_image = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
                self.change_pixmap_signal.emit(q_img)
            else:
                self.msleep(10) # wait if no frame is available

    def stop(self):
        self._run_flag = False
        self.wait()
        if self.cap.isOpened():
            self.cap.release()

    def set_camera(self, index):
        self.cam_index = index
        self.cam_change_requested = True

    def set_resolution(self, w, h):
        self.req_w = w
        self.req_h = h
        self.res_change_requested = True


class CameraApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle(APP_NAME)
        self.resize(1024, 768)
        self.setStyleSheet(self.get_stylesheet())

        # Session variables
        self.session_id = uuid.uuid4().hex[:4].upper()
        self.current_shot = 0
        self.is_shooting = False
        self.current_dir = DEFAULT_DIR
        self.gallery_paths = []
        self.preview_index = -1
        self.thumb_loader = None
        
        os.makedirs(self.current_dir, exist_ok=True)

        self.init_ui()

        # Thread setup
        self.thread = CameraThread()
        self.thread.change_pixmap_signal.connect(self.update_image)
        self.thread.image_saved_signal.connect(self.on_image_saved)
        self.thread.capture_finished_signal.connect(self.on_capture_finished)
        self.thread.start()

        # Initial Load of directory
        self.load_directory()

    def get_stylesheet(self):
        return """
            QMainWindow, QWidget { background-color: #1e1e2e; color: #cdd6f4; font-family: sans-serif; }
            QLabel { color: #cdd6f4; }
            QPushButton { background-color: #313244; color: #cdd6f4; border-radius: 6px; padding: 8px 16px; font-weight: bold; border: 1px solid #45475a; }
            QPushButton:hover { background-color: #45475a; }
            QPushButton:pressed { background-color: #585b70; }
            QPushButton:disabled { background-color: #181825; color: #585b70; border: 1px solid #313244;}
            QComboBox, QSpinBox { background-color: #313244; color: #cdd6f4; padding: 5px; border-radius: 4px; border: 1px solid #45475a;}
            QCheckBox { spacing: 8px; font-weight: bold;}
            QListWidget { background-color: #11111b; border: 1px solid #313244; border-radius: 8px; padding: 5px; }
            QListWidget::item:selected { background-color: #45475a; border-radius: 4px;}
        """

    def init_ui(self):
        # MAIN STACK
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # PAGE 0: CAMERA VIEW
        self.camera_page = QWidget()
        main_layout = QVBoxLayout(self.camera_page)

        # TOP BAR
        top_bar = QLabel()
        top_bar.setAlignment(Qt.AlignCenter)
        
        # Try to load the SVG logo
        logo_pixmap = QPixmap("CAMpy.svg")
        if not logo_pixmap.isNull():
            # Scale to a clean height while keeping aspect ratio smooth
            top_bar.setPixmap(logo_pixmap.scaledToHeight(60, Qt.SmoothTransformation))
        else:
            # Fallback to text if the SVG file is missing or unsupported
            top_bar.setText(APP_NAME)
            top_font = QFont()
            top_font.setPointSize(16)
            top_font.setBold(True)
            top_bar.setFont(top_font)
            
        main_layout.addWidget(top_bar)

        # MIDDLE SECTION
        middle_layout = QHBoxLayout()
        
        # --- LEFT PANEL ---
        left_panel = QVBoxLayout()
        left_panel.setAlignment(Qt.AlignTop)
        
        lbl_session = QLabel(f"SESSION ID: {self.session_id}")
        lbl_session.setStyleSheet("font-weight: bold; color: #a6e3a1;")
        
        self.chk_single = QCheckBox("SINGLE Image")
        self.chk_single.toggled.connect(self.on_single_toggled)

        self.spin_batches = QSpinBox()
        self.spin_batches.setRange(1, 20)
        self.spin_batches.setValue(4) # Updated default
        
        self.spin_batch_size = QSpinBox()
        self.spin_batch_size.setRange(1, 100)
        self.spin_batch_size.setValue(32)

        left_panel.addWidget(lbl_session)
        left_panel.addSpacing(20)
        left_panel.addWidget(QLabel("Capture Mode:"))
        left_panel.addWidget(self.chk_single)
        left_panel.addSpacing(10)
        left_panel.addWidget(QLabel("Number of Batches:"))
        left_panel.addWidget(self.spin_batches)
        left_panel.addWidget(QLabel("Batch Size:"))
        left_panel.addWidget(self.spin_batch_size)
        
        middle_layout.addLayout(left_panel, 1)

        # --- CENTER PANEL ---
        center_panel = QVBoxLayout()
        self.camera_label = ScaledLabel()
        self.btn_shoot = QPushButton("SHOOT")
        self.btn_shoot.setStyleSheet("background-color: #f38ba8; color: #11111b; font-size: 16px; padding: 15px;")
        self.btn_shoot.clicked.connect(self.start_shooting)
        
        center_panel.addWidget(self.camera_label, 1)
        center_panel.addWidget(self.btn_shoot)
        
        middle_layout.addLayout(center_panel, 3)

        # --- RIGHT PANEL ---
        right_panel = QVBoxLayout()
        right_panel.setAlignment(Qt.AlignTop)

        self.combo_camera = QComboBox()
        self.combo_camera.addItems(["Camera 0", "Camera 1", "Camera 2", "Camera 3"])
        self.combo_camera.currentIndexChanged.connect(self.change_camera)

        self.combo_res = QComboBox()
        self.combo_res.addItems(["640x480", "800x600", "1280x720", "1920x1080"])
        self.combo_res.currentTextChanged.connect(self.change_resolution)

        self.combo_format = QComboBox()
        self.combo_format.addItems(["1:1", "4:3", "16:9"])
        self.combo_format.currentTextChanged.connect(self.change_format)

        self.btn_dir = QPushButton("Select Roll Directory")
        self.btn_dir.clicked.connect(self.select_directory)
        
        self.lbl_dir = QLabel(self.current_dir)
        self.lbl_dir.setWordWrap(True)
        self.lbl_dir.setStyleSheet("font-size: 10px; color: #a6adc8;")

        right_panel.addWidget(QLabel("Camera Device:"))
        right_panel.addWidget(self.combo_camera)
        right_panel.addSpacing(15)
        right_panel.addWidget(QLabel("Lens Resolution:"))
        right_panel.addWidget(self.combo_res)
        right_panel.addSpacing(15)
        right_panel.addWidget(QLabel("Aspect Format:"))
        right_panel.addWidget(self.combo_format)
        right_panel.addSpacing(15)
        right_panel.addWidget(self.btn_dir)
        right_panel.addWidget(self.lbl_dir)

        middle_layout.addLayout(right_panel, 1)
        main_layout.addLayout(middle_layout, 1)

        # --- BOTTOM BAR (ROLL) ---
        self.gallery_list = QListWidget()
        self.gallery_list.setFixedHeight(140)
        self.gallery_list.setViewMode(QListView.IconMode)
        self.gallery_list.setIconSize(QSize(120, 100))
        self.gallery_list.setFlow(QListView.LeftToRight)
        self.gallery_list.setWrapping(False)
        self.gallery_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.gallery_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.gallery_list.setSpacing(10)
        self.gallery_list.itemClicked.connect(self.on_thumbnail_clicked)
        
        main_layout.addWidget(self.gallery_list)

        self.stacked_widget.addWidget(self.camera_page)

        # PAGE 1: PREVIEW MODE
        self.preview_page = QWidget()
        preview_layout = QVBoxLayout(self.preview_page)
        
        nav_layout = QHBoxLayout()
        self.btn_back = QPushButton("◀ Back to Camera")
        self.btn_back.clicked.connect(self.exit_preview)
        nav_layout.addWidget(self.btn_back)
        nav_layout.addStretch()
        
        self.lbl_preview_info = QLabel("")
        nav_layout.addWidget(self.lbl_preview_info)
        preview_layout.addLayout(nav_layout)

        self.preview_label = ScaledLabel()
        preview_layout.addWidget(self.preview_label, 1)

        controls_layout = QHBoxLayout()
        self.btn_prev = QPushButton("◀ Previous (Left Key)")
        self.btn_prev.clicked.connect(self.prev_image)
        self.btn_next = QPushButton("Next (Right Key) ▶")
        self.btn_next.clicked.connect(self.next_image)
        
        controls_layout.addStretch()
        controls_layout.addWidget(self.btn_prev)
        controls_layout.addSpacing(20)
        controls_layout.addWidget(self.btn_next)
        controls_layout.addStretch()
        preview_layout.addLayout(controls_layout)

        self.stacked_widget.addWidget(self.preview_page)

    def on_single_toggled(self, checked):
        self.spin_batches.setEnabled(not checked)
        self.spin_batch_size.setEnabled(not checked)
        
    def change_camera(self, index):
        self.thread.set_camera(index)

    def change_resolution(self, text):
        w, h = map(int, text.split('x'))
        self.thread.set_resolution(w, h)

    def change_format(self, text):
        self.thread.current_format = text

    def select_directory(self):
        d = QFileDialog.getExistingDirectory(self, "Select Roll Directory", self.current_dir)
        if d:
            self.current_dir = d
            self.lbl_dir.setText(d)
            self.load_directory()

    def update_image(self, qimg):
        if self.is_shooting:
            # Draw Recording LED
            painter = QPainter(qimg)
            painter.setBrush(QBrush(Qt.red))
            painter.setPen(Qt.NoPen)
            radius = 12
            painter.drawEllipse(qimg.width() - radius*2 - 15, 15, radius*2, radius*2)
            painter.end()

        self.camera_label.setPixmap(QPixmap.fromImage(qimg))

    def start_shooting(self):
        self.is_shooting = True
        self.btn_shoot.setEnabled(False)
        self.btn_shoot.setText("TAKING PICTURES...")
        self.btn_shoot.setStyleSheet("background-color: #313244; color: #a6adc8; font-size: 16px; padding: 15px;")
        
        queue = []
        is_single = self.chk_single.isChecked()
        
        if is_single:
            filename = f"{self.session_id}_{self.current_shot}-1.png"
            queue.append(os.path.join(self.current_dir, filename))
        else:
            batches = self.spin_batches.value()
            b_size = self.spin_batch_size.value()
            for b in range(1, batches + 1):
                for p in range(1, b_size + 1):
                    filename = f"{self.session_id}_{self.current_shot}b{b}-{p}.png"
                    queue.append(os.path.join(self.current_dir, filename))
                    
        self.current_shot += 1
        self.thread.capture_queue = queue

    def on_image_saved(self, filepath):
        # Dynamically append to gallery without reloading whole directory
        self.gallery_paths.append(filepath)
        img = QImage(filepath)
        if not img.isNull():
            # Convert QImage to QPixmap and QIcon safely on the main GUI thread
            pixmap = QPixmap.fromImage(img).scaled(120, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon = QIcon(pixmap)
            item = QListWidgetItem(icon, os.path.basename(filepath))
            item.setData(Qt.UserRole, filepath)
            self.gallery_list.addItem(item)
            self.gallery_list.scrollToBottom()

    def on_capture_finished(self):
        self.is_shooting = False
        self.btn_shoot.setEnabled(True)
        self.btn_shoot.setText("SHOOT")
        self.btn_shoot.setStyleSheet("background-color: #f38ba8; color: #11111b; font-size: 16px; padding: 15px;")

    def load_directory(self):
        if self.thumb_loader and self.thumb_loader.isRunning():
            self.thumb_loader.stop()

        self.gallery_list.clear()
        self.gallery_paths.clear()
        
        os.makedirs(self.current_dir, exist_ok=True)

        self.thumb_loader = ThumbnailLoader(self.current_dir)
        self.thumb_loader.thumbnail_loaded.connect(self.add_thumbnail_to_ui)
        self.thumb_loader.start()

    def add_thumbnail_to_ui(self, path, qimg):
        self.gallery_paths.append(path)
        filename = os.path.basename(path)
        
        # Convert QImage to QPixmap and QIcon safely on the main GUI thread
        pixmap = QPixmap.fromImage(qimg)
        icon = QIcon(pixmap)
        
        item = QListWidgetItem(icon, filename)
        item.setData(Qt.UserRole, path)
        self.gallery_list.addItem(item)

    def on_thumbnail_clicked(self, item):
        path = item.data(Qt.UserRole)
        if path in self.gallery_paths:
            self.preview_index = self.gallery_paths.index(path)
            self.show_preview()

    def show_preview(self):
        if 0 <= self.preview_index < len(self.gallery_paths):
            path = self.gallery_paths[self.preview_index]
            self.preview_label.setPixmap(QPixmap(path))
            self.lbl_preview_info.setText(f"{os.path.basename(path)} ({self.preview_index + 1}/{len(self.gallery_paths)})")
            self.stacked_widget.setCurrentIndex(1)

    def exit_preview(self):
        self.stacked_widget.setCurrentIndex(0)
        self.preview_label.setPixmap(QPixmap()) # free memory

    def prev_image(self):
        if self.preview_index > 0:
            self.preview_index -= 1
            self.show_preview()

    def next_image(self):
        if self.preview_index < len(self.gallery_paths) - 1:
            self.preview_index += 1
            self.show_preview()

    def keyPressEvent(self, event):
        if self.stacked_widget.currentIndex() == 1:
            if event.key() == Qt.Key_Left:
                self.prev_image()
            elif event.key() == Qt.Key_Right:
                self.next_image()
            elif event.key() == Qt.Key_Escape:
                self.exit_preview()
        super().keyPressEvent(event)

    def closeEvent(self, event):
        self.thread.stop()
        if self.thumb_loader:
            self.thumb_loader.stop()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = CameraApp()
    window.show()
    sys.exit(app.exec_())