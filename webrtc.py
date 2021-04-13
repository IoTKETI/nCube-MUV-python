# -*-coding:utf-8 -*-

"""
 Created by Wonseok Jung in KETI on 2021-03-16.
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

import http_app

import time, sys, requests, json, uuid, random, string

display_name = ''
session_id = ''
handle_id = ''
room_number = ''
count = 0


def rand_var():
    rand_str = ''
    for i in range(12):
        rand_str += str(random.choice(string.ascii_letters + string.digits))

    return rand_str


def openWeb():
    opt = Options()
    opt.add_argument("--disable-infobars")
    opt.add_argument("start-maximized")
    opt.add_argument("--disable-extensions")
    opt.add_argument('--ignore-certificate-errors')
    opt.add_argument('--ignore-ssl-errors')

    opt.add_experimental_option("prefs", {
        "profile.default_content_setting_values.media_stream_mic": 1,
        "profile.default_content_setting_values.media_stream_camera": 1
    })

    capabilities = DesiredCapabilities.CHROME
    capabilities['goog:loggingPrefs'] = {'browser': 'ALL'}

    if sys.platform.startswith('win'):  # Windows
        driver = webdriver.Chrome(chrome_options=opt, desired_capabilities=capabilities, executable_path='chromedriver')
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):  # Linux and Raspbian
        driver = webdriver.Chrome(chrome_options=opt, desired_capabilities=capabilities, executable_path='/usr/lib/chromium-browser/chromedriver')
    elif sys.platform.startswith('darwin'):  # MacOS
        driver = webdriver.Chrome(chrome_options=opt, desired_capabilities=capabilities, executable_path='/usr/local/bin/chromedriver')
    else:
        raise EnvironmentError('Unsupported platform')

    driver.get("https://203.253.128.177/videoroomtest.html")

    wait = WebDriverWait(driver, 10)
    element = wait.until(EC.element_to_be_clickable((By.ID, 'start')))
    # time.sleep(5)
    control_web(driver)


def control_web(driver):
    global display_name
    global session_id
    global handle_id
    global room_number
    global flag

    button_id = driver.find_element_by_id('start')
    button_id.click()

    time.sleep(1)

    for entry in driver.get_log('browser'):
        level = entry['level']
        if level == 'INFO':
            log_t = entry['message'].split(' ')
            if log_t[3] == 'session:':
                session_id = log_t[4][:-1]
            elif log_t[3] == 'handle:':
                handle_id = log_t[4][:-1]

    room_number = http_app.drone_info["room"]
    rsc, res_body = crt_room(session_id, handle_id, room_number)

    driver.implicitly_wait(5)
    time.sleep(2)

    Room_Number = driver.find_element_by_id('roomnumber')
    Room_Number.send_keys(room_number)

    username_id = driver.find_element_by_id('username')
    username_id.send_keys(display_name)
    username_id.send_keys(Keys.RETURN)

    # register_id = driver.find_element_by_id('register')
    # register_id.click()
    while True:
        pass
        # time.sleep(10)
        # get_participants()


def crt_room(session_id, handle_id, room_number):
    # global session_id
    # global handle_id

    url = "http://" + http_app.drone_info["host"] + ":8088/janus"

    payload = json.dumps({
        "janus": "message",
        "transaction": rand_var(),
        "session_id": int(session_id),
        "handle_id": int(handle_id),
        "body": {
            "request": "create",
            "room": int(room_number),
            "publishers": 6,
            "description": "drone",
            "secret": "keti",
            "is_private": False,
            "bitrate": 512000,
            "fir_freq": 10,
            "videocodec": "vp9",
            "video_svc": True
        }
    })
    headers = {
        'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    try:
        rsc = response.json()['plugindata']['data']['error_code']
        res_body = response.json()['plugindata']['data']['error']
        print('WebRTC --> [rsc:' + str(rsc) + '] ' + res_body)
        with open("webrtc_log.txt", "w") as f:
            f.write("Error in crt_room(): " + 'WebRTC --> [rsc:' + str(rsc) + '] ' + res_body)

        return rsc, res_body
    except:
        rsc = 201
        res_body = 'success create [ {} ] room'.format(room_number)
        print('WebRTC --> [' + str(rsc) + '] ' + res_body)

        return rsc, res_body


def destroy_room():
    global session_id
    global handle_id
    global room_number

    url = "http://" + http_app.drone_info["host"] + ":8088/janus"

    payload = json.dumps({
        "janus": "message",
        "transaction": "9qLWxeUm2XqH",
        "session_id": int(session_id),
        "handle_id": int(handle_id),
        "body": {
            "request": "destroy",
            "room": int(room_number),
            "secret": "keti"
        }
    })
    headers = {
        'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    try:
        rsc = response.json()['plugindata']['data']['error_code']
        res_body = response.json()['plugindata']['data']['error']
        print('WebRTC --> [rsc:' + str(rsc) + '] ' + res_body)
        if rsc == 427:
            pass
        else:
            with open("webrtc_log.txt", "w") as f:
                f.write("Error in destroy_room(): " + 'WebRTC --> [rsc:' + str(rsc) + '] ' + res_body)
        return rsc, res_body
    except Exception as e:
        rsc = 201
        res_body = 'success create [ {} ] room'.format(room_number)
        print('WebRTC --> [' + str(rsc) + '] ' + res_body)

        return rsc, res_body


def get_participants():
    global session_id
    global handle_id
    global room_number
    global count

    url = "http://" + http_app.drone_info["host"] + ":8088/janus"

    payload = json.dumps({
        "janus": "message",
        "transaction": "Ik7z2RcMbxgO",
        "session_id": int(session_id),
        "handle_id": int(handle_id),
        "body": {
            "request": "listparticipants",
            "room": int(room_number)
        }
    })
    headers = {
        'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    try:
        res = response.json()['plugindata']['data']
        if res.get('participants'):
            num_participants = len(res['participants'])
            if num_participants < 1:
                count += 1
                if count > 3:
                    with open("webrtc_log.txt", "w") as f:
                        f.write("Error in get_participants(): No users have joined the room.")
        else:
            print('Destroy Room [ {} ]'.format(room_number))
            destroy_room()
    except:
        with open("webrtc_log.txt", "w") as f:
            f.write("Error in get_participants(): except")
        pass


def webrtc():
    global display_name

    display_name = http_app.drone_info["drone"]

    if display_name.isalnum():
        pass
    else:
        display_name = ''.join(char for char in display_name if char.isalnum())
    openWeb()


"""
# from PyQt5.QtWidgets import QApplication
# from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
# from PyQt5.QtCore import QUrl
# from PyQt5 import QtNetwork, QtWebEngineWidgets

import json
import threading
import time

import pyautogui

from PySide2.QtWidgets import QApplication
from PySide2.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PySide2.QtCore import QUrl
from PySide2 import QtNetwork, QtWebEngineWidgets

import http_app


def set_ssl_protocol():
    default_config = QtNetwork.QSslConfiguration.defaultConfiguration()
    default_config.setProtocol(QtNetwork.QSsl.TlsV1_2)
    QtNetwork.QSslConfiguration.setDefaultConfiguration(default_config)


class WebEnginePage(QtWebEngineWidgets.QWebEnginePage):
    def __init__(self, *args, **kwargs):
        QWebEnginePage.__init__(self, *args, **kwargs)
        self.featurePermissionRequested.connect(self.onFeaturePermissionRequested)

    def onFeaturePermissionRequested(self, url, feature):
        if feature in (QWebEnginePage.MediaAudioCapture,
                       QWebEnginePage.MediaVideoCapture,
                       QWebEnginePage.MediaAudioVideoCapture):
            self.setFeaturePermission(url, feature, QWebEnginePage.PermissionGrantedByUser)
        else:
            self.setFeaturePermission(url, feature, QWebEnginePage.PermissionDeniedByUser)

    def certificateError(self, certificateError):
        # print(certificateError.errorDescription(), certificateError.url(), certificateError.isOverridable())
        error = certificateError.error()
        if error == QtWebEngineWidgets.QWebEngineCertificateError.SslPinnedKeyNotInCertificateChain: # -150
            print("{} - SslPinnedKeyNotInCertificateChain".format(error))
        elif error == QtWebEngineWidgets.QWebEngineCertificateError.CertificateCommonNameInvalid: # -200
            print("{} - CertificateCommonNameInvalid".format(error))
        elif error == QtWebEngineWidgets.QWebEngineCertificateError.CertificateDateInvalid: # -201
            print("{} - CertificateDateInvalid".format(error))
        elif error == QtWebEngineWidgets.QWebEngineCertificateError.CertificateAuthorityInvalid: # -202
            # print("{} - CertificateAuthorityInvalid".format(error))
            certificateError.ignoreCertificateError()
        elif error == QtWebEngineWidgets.QWebEngineCertificateError.CertificateContainsErrors: # -203
            print("{} - CertificateContainsErrors".format(error))
        if error == QtWebEngineWidgets.QWebEngineCertificateError.CertificateNoRevocationMechanism: # -204
            print("{} - CertificateNoRevocationMechanism".format(error))
        elif error == QtWebEngineWidgets.QWebEngineCertificateError.CertificateUnableToCheckRevocation: # -205
            print("{} - CertificateUnableToCheckRevocation".format(error))
        elif error == QtWebEngineWidgets.QWebEngineCertificateError.CertificateRevoked: # -206
            print("{} - CertificateRevoked".format(error))
        elif error == QtWebEngineWidgets.QWebEngineCertificateError.CertificateInvalid: # -207
            print("{} - CertificateAuthorityInvalid".format(error))
        elif error == QtWebEngineWidgets.QWebEngineCertificateError.CertificateWeakSignatureAlgorithm: # -208
            print("{} - CertificateWeakSignatureAlgorithm".format(error))
        elif error == QtWebEngineWidgets.QWebEngineCertificateError.CertificateNonUniqueName: # -210
            print("{} - CertificateNonUniqueName".format(error))
        elif error == QtWebEngineWidgets.QWebEngineCertificateError.CertificateWeakKey: # -211
            print("{} - CertificateWeakKey".format(error))
        elif error == QtWebEngineWidgets.QWebEngineCertificateError.CertificateNameConstraintViolation: # -212
            print("{} - CertificateNameConstraintViolation".format(error))
        elif error == QtWebEngineWidgets.QWebEngineCertificateError.CertificateValidityTooLong: # -213
            print("{} - CertificateValidityTooLong".format(error))
        elif error == QtWebEngineWidgets.QWebEngineCertificateError.CertificateTransparencyRequired: # -214
            print("{} - CertificateTransparencyRequired".format(error))
        elif error == QtWebEngineWidgets.QWebEngineCertificateError.CertificateKnownInterceptionBlocked: # -217
            print("{} - CertificateKnownInterceptionBlocked".format(error))

        return super(WebEnginePage, self).certificateError(certificateError)


def auto_control():
    try:
        display_name = http_app.drone_info["drone"]
        if display_name.isalnum():
            pass
        else:
            display_name = ''.join(char for char in display_name if char.isalnum())
        print(display_name)

        pyautogui.moveTo(938, 430)
        time.sleep(3)
        pyautogui.click()
        pyautogui.typewrite(display_name, interval=0.1)
        pyautogui.keyDown('enter')
        pyautogui.keyUp('enter')
    except Exception as e:
        print(e)


def webrtc():
    # 좌표 객체 얻기
    position = pyautogui.position()

    # 화면 전체 크기 확인하기
    print('Monitor Size: ', pyautogui.size())
    # 현재 마우스 커서 위치 확인
    print('cur_cursor_position: ', pyautogui.position())

    app = QApplication([])

    view = QWebEngineView()
    page = WebEnginePage()
    view.setPage(page)
    view.load(QUrl("https://203.253.128.177/videoroomtest.html"))
    view.setGeometry(300, 300, 1500, 1200)
    view.setWindowTitle('Drone Broadcast')
    t = threading.Thread(target=auto_control)
    t.start()
    view.show()
    app.exec_()
"""
