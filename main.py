from PyQt5.QtWidgets import (QApplication, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, 
                             QFileDialog, QSlider, QRadioButton, QMessageBox, QButtonGroup, QPlainTextEdit, QGroupBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from num2words import num2words
import requests
import os
from pydub import AudioSegment
import subprocess
from datetime import datetime
import queue
import threading
import subprocess
import json

def transliterate(name):
    # Словарь с заменами
    slovar = {'a':'а', 'b':'б', 'v':'в', 'g':'г', 'd':'д', 'e':'е', 'yo':'ё', 'zh':'ж',
    'z':'з', 'i':'и', 'j':'й', 'k':'к', 'l':'л', 'm':'м', 'n':'н', 'o':'о', 'p':'п',
    'r':'р', 's':'с', 't':'т', 'u':'у', 'f':'ф', 'h':'х', 'c':'ц', 'ch':'ч', 'sh':'ш',
    'sch':'щ', 'y':'ы', 'e':'э', 'yu':'ю', 'ya':'я', 'x':'кс', 'w':'в', 'q':'к'}

    # Заменяем каждую букву в введенной строке
    for key in slovar:
        name = name.replace(key, slovar[key])
    return name

def convert_numbers_to_words(text):
    words = text.split()
    for i in range(len(words)):
        if words[i].isdigit():
            words[i] = num2words(words[i], lang='ru')
    return ' '.join(words)

def process_text(text):
    text = transliterate(text)
    text = convert_numbers_to_words(text)
    return text

class Worker(threading.Thread):
    def __init__(self, queue, mainWindow):
        super().__init__()
        self.queue = queue
        self.mainWindow = mainWindow

    def run(self):
        while True:
            task = self.queue.get()
            if task is None:
                break
            script_path, params_string = task
            process = subprocess.Popen(['venv/scripts/python.exe', script_path] + params_string.split())
            process.wait()  # wait for the process to finish
            self.queue.task_done()
            self.mainWindow.update_ui.emit(params_string)
            self.mainWindow.update_queue.emit(self.queue.qsize())  # emit signal with the queue size


class MainWindow(QWidget):
    update_ui = pyqtSignal(str)
    update_queue = pyqtSignal(int)  # new signal to update the queue size


    def __init__(self):
        super().__init__()

        self.update_ui.connect(self.on_worker_finished)
        self.update_queue.connect(self.on_queue_updated)  # connect the signal to a new slot


        self.q = queue.Queue()
        self.worker = Worker(self.q, self)
        self.worker.start()


        self.model_index_path = ""
        self.model_path = ""
        self.outpath_path = "out"

        # Создаем горизонтальный layout
        self.main_layout = QHBoxLayout()
        self.settings_layout = QVBoxLayout()
        self.text_layout = QVBoxLayout()

        self.voice_button = QPushButton('Озвучить')
        self.clear_text_button = QPushButton('Очистить')
        self.load_text_button = QPushButton('Загрузить из файла')


        self.clear_text_button.clicked.connect(self.clear_text)
        self.load_text_button.clicked.connect(self.load_text_from_file)
        self.voice_button.clicked.connect(self.voice_text)

        self.audio_path = None
        

        # Создаем поля

        self.pith_slider, self.pith_slider_label = self.create_slider_and_label(-24, 24, 0, 'pith')
        self.settings_layout.addWidget(self.pith_slider_label)
        self.settings_layout.addWidget(self.pith_slider)

        self.model_path_button = QPushButton('выбрать')
        self.model_path_button.clicked.connect(lambda: self.open_file_dialog(self.model_path_button))
        self.settings_layout.addWidget(QLabel('Укажите путь к модели:'))
        self.settings_layout.addWidget(self.model_path_button)

        self.model_index_button = QPushButton('выбрать')
        self.model_index_button.clicked.connect(lambda: self.open_file_dialog(self.model_index_button))
        self.settings_layout.addWidget(QLabel('Укажите индекс файл (опционально):'))
        self.settings_layout.addWidget(self.model_index_button)

        self.method_group, self.method_buttons = self.create_radio_group(['harverst', 'crepe', 'mangio-crepe', 'rmvpe'])
        self.method_buttons['crepe'].setChecked(True)
        self.settings_layout.addWidget(QLabel('method'))
        self.settings_layout.addWidget(self.method_group)

        self.voice_model_group, self.voice_model_buttons = self.create_radio_group(['aidar', 'eugene', 'kseniya', 'xenia', 'baya'])
        self.voice_model_buttons['aidar'].setChecked(True)
        self.settings_layout.addWidget(QLabel('Выберите голос модели:'))
        self.settings_layout.addWidget(self.voice_model_group)
        

        # self.settings_layout.addWidget(QLabel('method'))
        # self.settings_layout.addWidget(self.method_group)

        self.outpath_button = QPushButton('выбрать')
        self.outpath_button.clicked.connect(self.open_folder_dialog)
        self.settings_layout.addWidget(QLabel('Выберите папку вывода: (опционально, по умолчанию out)'))
        self.settings_layout.addWidget(self.outpath_button)

        self.index_ratio_slider, self.index_ratio_slider_label = self.create_slider_and_label(0, 100, 50, 'index_ratio')
        self.settings_layout.addWidget(self.index_ratio_slider_label)
        self.settings_layout.addWidget(self.index_ratio_slider)

        # self.device_group, self.device_buttons = self.create_radio_group(['cpu', 'cuda:0'])
        # self.device_buttons['cuda:0'].setChecked(True)
        # self.settings_layout.addWidget(QLabel('device'))
        # self.settings_layout.addWidget(self.device_group)

        self.protect_voice_slider, self.protect_voice_slider_label = self.create_slider_and_label(0, 50, 33, 'protect_voice')
        self.settings_layout.addWidget(self.protect_voice_slider_label)
        self.settings_layout.addWidget(self.protect_voice_slider)

        self.mangio_crepe_hop_slider, self.mangio_crepe_hop_slider_label = self.create_slider_and_label(64, 256, 128, 'mangio_crepe_hop')
        self.settings_layout.addWidget(self.mangio_crepe_hop_slider_label)
        self.settings_layout.addWidget(self.mangio_crepe_hop_slider)

        self.speech_speed_slider, self.speech_speed_slider_label = self.create_slider_and_label(51, 150, 100, 'speech_speed')
        self.settings_layout.addWidget(self.speech_speed_slider_label)
        self.settings_layout.addWidget(self.speech_speed_slider)

        self.text_field = QPlainTextEdit()
        self.text_layout.addWidget(QLabel('text'))
        self.text_layout.addWidget(self.text_field)

        self.settings_layout.addWidget(self.voice_button)

        self.text_layout.addWidget(self.clear_text_button)
        self.text_layout.addWidget(self.load_text_button)

        # Добавляем layouts на главное окно
        self.main_layout.addLayout(self.text_layout)
        self.main_layout.addLayout(self.settings_layout)

        self.setLayout(self.main_layout)

        # Save setting on save
        self.pith_slider.valueChanged.connect(self.save_settings)
        self.model_path_button.clicked.connect(self.save_settings)
        self.model_index_button.clicked.connect(self.save_settings)
        for button in self.method_buttons.values():
            button.clicked.connect(self.save_settings)
        for button in self.voice_model_buttons.values():
            button.clicked.connect(self.save_settings)
        self.outpath_button.clicked.connect(self.save_settings)
        self.index_ratio_slider.valueChanged.connect(self.save_settings)
        # for button in self.device_buttons.values():
        #     button.clicked.connect(self.save_settings)
        self.protect_voice_slider.valueChanged.connect(self.save_settings)
        self.mangio_crepe_hop_slider.valueChanged.connect(self.save_settings)
        self.speech_speed_slider.valueChanged.connect(self.save_settings)

        self.load_settings()

    def on_worker_finished(self, params_string):
        QMessageBox.information(self, "Успех", f"Аудиофайл успешно преобразован.")

    def on_queue_updated(self, queue_size):
        self.setWindowTitle(f"Запросов в очереди: {queue_size}")

    def save_settings(self):
        settings = {
            "pith": self.pith_slider.value(),
            "model_index": self.model_index_path,
            "method": self.get_selected_button(self.method_buttons),
            "outpath": self.outpath_path,
            "model_path": self.model_path,
            "index_ratio": self.index_ratio_slider.value(),
            # "device": self.get_selected_button(self.device_buttons),
            "protect_voice": self.protect_voice_slider.value(),
            "mangio_crepe_hop": self.mangio_crepe_hop_slider.value(),
        }
        with open("settings.json", "w") as file:
            json.dump(settings, file)

    def load_settings(self):
        try:
            with open("settings.json", "r") as file:
                settings = json.load(file)

            self.pith_slider.setValue(settings["pith"])
            self.model_index_path = settings["model_index"]
            self.outpath_path = settings["outpath"]
            self.model_path = settings["model_path"]
            self.index_ratio_slider.setValue(settings["index_ratio"])
            self.protect_voice_slider.setValue(settings["protect_voice"])
            self.mangio_crepe_hop_slider.setValue(settings["mangio_crepe_hop"])

            # Вызовите метод для установки выбранного радиокнопки
            self.set_selected_button(self.method_buttons, settings["method"])
            # self.set_selected_button(self.device_buttons, settings["device"])

            if self.model_index_path:
                self.model_index_button.setText(self.model_index_path)
            if self.model_path:
                self.model_path_button.setText(self.model_path)
        except FileNotFoundError:
            pass  # файл с настройками не найден, возможно, это первый запуск приложения

    def create_slider_and_label(self, min_value, max_value, default_value, label):
        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(min_value)
        slider.setMaximum(max_value)
        slider.setValue(default_value)
        slider.valueChanged.connect(lambda: self.update_slider_label(slider, label_label))
        value = default_value / 100 if label == 'index_ratio' else default_value
        label_label = QLabel(f'{label}: {value}')
        return slider, label_label

    def update_slider_label(self, slider, label):
        value = slider.value() / 100 if label.text().split(":")[0] == 'index_ratio' else slider.value()
        label.setText(f'{label.text().split(":")[0]}: {value}')

    def create_radio_group(self, options):
        radio_group = QButtonGroup(self)
        layout = QVBoxLayout()
        radio_buttons = {}

        for option in options:
            radio_button = QRadioButton(option)
            radio_group.addButton(radio_button)
            layout.addWidget(radio_button)
            radio_buttons[option] = radio_button

        widget = QWidget()
        widget.setLayout(layout)

        return widget, radio_buttons


    def open_file_dialog(self, button):
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(self,"QFileDialog.getOpenFileName()", "","All Files (*);;Python Files (*.py)", options=options)

        if fileName:
            # Если файл был выбран, обновляем соответствующую переменную и текст кнопки
            if button == self.model_index_button:
                self.model_index_path = fileName
                self.model_index_button.setText(f"{fileName}")
            elif button == self.model_path_button:
                self.model_path = fileName
                self.model_path_button.setText(f"{fileName}")
        else:
            # Если файл не был выбран, сбрасываем значение переменной и текст кнопки
            if button == self.model_index_button:
                self.model_index_path = ""
                self.model_index_button.setText("Выберите файл")
            elif button == self.model_path_button:
                self.model_path = ""
                self.model_path_button.setText("Выберите файл")

    def open_folder_dialog(self):
        options = QFileDialog.Options()
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку", "", options=options)
        if folder:
            self.outpath_button.setText(f"{folder}")



    def clear_text(self):
        self.text_field.clear()

    def set_selected_button(self, button_group, button_text):
        for button in button_group.values():
            if button.text() == button_text:
                button.setChecked(True)
                break

    def load_text_from_file(self):
        file_name = QFileDialog.getOpenFileName(self, 'Open file', '/home')[0]
        if file_name:
            with open(file_name, 'r', encoding='utf-8') as file:
                self.text_field.setPlainText(file.read())

    def get_selected_button(self, button_group):
        for button in button_group.values():
            if button.isChecked():
                return button.text()

    def voice_text(self):
        url = "http://127.0.0.1:8080/tts/generate"
        data = {
            "speaker": self.get_selected_button(self.voice_model_buttons),
            "text": process_text(self.text_field.toPlainText()),
            "session": "generate"
        }
        try:
            response = requests.post(url, json=data)
            if response.status_code != 200:
                QMessageBox.warning(self, "Ошибка", f"Не удалось выполнить запрос: {response.text}")
            else:
                # Создаем папку temp, если она не существует
                os.makedirs('temp', exist_ok=True)

                self.audio_path = 'temp/audio.wav'
                # Сохраняем аудиофайл в папку temp
                with open('temp/audio.wav', 'wb') as audio:
                    audio.write(response.content)

                # Изменяем скорость аудио
                sound = AudioSegment.from_wav('temp/audio.wav')
                sound.speedup(playback_speed=self.speech_speed_slider.value()/100.0)
                sound.export('temp/audio.wav', format='wav')

                # Создаем строку с параметрами
                pith = str(self.pith_slider.value())
                model_index = str(self.model_index_path) if self.model_index_path else "''"
                method = self.get_selected_button(self.method_buttons)  # Теперь возвращает текст
                outpath = self.outpath_path
                model_path = str(self.model_path)
                index_ratio = str(self.index_ratio_slider.value() / 100)
                device = "cuda:0"  # Теперь возвращает текст
                protect_voice = str(self.protect_voice_slider.value() / 100)
                mangio_crepe_hop = str(self.mangio_crepe_hop_slider.value())

                now = datetime.now()
                # Преобразуем в строку в формате "YYYYMMDD-HHMMSS"
                filename = "/" + now.strftime("%Y%m%d-%H%M%S") + '.mp3'

                outpath += filename

                params_string = f"{pith} {self.audio_path} {model_index} {method} {outpath} {model_path} {index_ratio} {device} True 3 0 1 {protect_voice} {mangio_crepe_hop}"

                script_path = 'libs/rvc/test-infer.py'

                self.q.put((script_path, params_string))
                self.update_queue.emit(self.q.qsize())

        except requests.exceptions.RequestException as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось выполнить запрос: {str(e)}")


app = QApplication([])
window = MainWindow()
window.show()
app.exec_()