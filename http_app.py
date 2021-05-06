# -*-coding:utf-8 -*-

"""
 Created by Wonseok Jung in KETI on 2021-03-16.
"""

import paho.mqtt.client as mqtt
from urllib.parse import urlparse
import os, sys, shutil, platform, socket, random, time, subprocess, json, uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import threading
from functools import wraps

import thyme
import conf
import noti
import thyme_tas_mav as tas_mav
import http_adn

HTTP_SUBSCRIPTION_ENABLE = 0
MQTT_SUBSCRIPTION_ENABLE = 0

my_gcs_name = ''
my_parent_cnt_name = ''
my_cnt_name = ''
pre_my_cnt_name = ''
my_mission_parent = ''
my_mission_name = ''
my_sortie_name = 'disarm'

my_drone_type = 'pixhawk'
my_secure = 'off'
my_system_id = 8

Req_auth = ''
Res_auth = ''
Result_auth = ''
Certification = ''

retry_interval = 2500
normal_interval = 100

authResult = 'yet'

server = None
mqtt_flag = ''
noti_topic = ''
muv_sub_gcs_topic = ''

muv_sub_msw_topic = []

muv_pub_fc_gpi_topic = ''
muv_pub_fc_hb_topic = ''

msw_package = ''
webrtc_room_number = 0

def delay(delay=0.):
    """
    Decorator delaying the execution of a function for a while.
    """

    def wrap(f):
        @wraps(f)
        def delayed(*args, **kwargs):
            timer = threading.Timer(delay, f, args=args, kwargs=kwargs)
            timer.start()

        return delayed

    return wrap


class Timer:
    toClearTimer = False

    def setTimeout(self, fn, time):
        isInvokationCancelled = False

        @delay(time)
        def some_fn():
            if self.toClearTimer is False:
                fn()
            else:
                pass

        some_fn()
        return isInvokationCancelled

    def setClearTimer(self):
        self.toClearTimer = True


def getType(p):
    type = 'string'
    if isinstance(p, list):
        type = 'list'
    elif isinstance(p, str):
        try:
            if isinstance(p, dict):
                type = 'string_dictionary'
            else:
                type = 'string'
        except Exception as e:
            type = 'string'
            return type
    elif (p is not None) and (isinstance(p, dict)):
        type = 'dictionary'
    else:
        type = 'other'
    return type


# ready for mqtt
for i in range(0, len(conf.conf['sub'])):
    if conf.conf['sub'][i]['name'] is not None:
        if urlparse(conf.conf['sub'][i]['nu']).scheme == 'http':
            HTTP_SUBSCRIPTION_ENABLE = 1
            if urlparse(conf.conf['sub'][i]['nu']).netloc == 'autoset':
                conf.conf.sub[i]['nu'] = 'http://' + socket.gethostbyname(socket.gethostname()) + ':' + conf.conf['ae'][
                    'port'] + urlparse(conf.conf['sub'][i]['nu'])['pathname']
        elif urlparse(conf.conf['sub'][i]['nu']).scheme == 'mqtt':
            MQTT_SUBSCRIPTION_ENABLE = 1
        else:
            print('notification uri of subscription is not supported')

return_count = 0
request_count = 0


def ready_for_notification():
    global noti_topic
    if HTTP_SUBSCRIPTION_ENABLE == 1:
        server = HTTPServer(('0.0.0.0', int(conf.conf['ae']['port'])), BaseHTTPRequestHandler)
        print('http_server running at {} port'.format(conf.conf['ae']['port']))
        server.serve_forever()

    if MQTT_SUBSCRIPTION_ENABLE == 1:
        for i in range(0, len(conf.conf['sub'])):
            if conf.conf['sub'][i]['name'] is not None:
                print(urlparse(conf.conf['sub'][i]['nu']).scheme, '==============================')
                if urlparse(conf.conf['sub'][i]['nu']).scheme == 'mqtt':
                    if urlparse(conf.conf['sub'][i]['nu']).netloc == 'autoset':
                        conf.conf['sub'][i]['nu'] = 'mqtt://' + conf.conf['cse']["host"] + '/' + conf.conf['ae']['id']
                        noti_topic = '/oneM2M/req/+/{}/#'.format(conf.conf['ae']['id'])
                    elif urlparse(conf.conf['sub'][i]['nu']).netloc == conf.conf['cse']["host"]:
                        noti_topic = '/oneM2M/req/+/{}/#'.format(conf.conf['ae']['id'])
                    else:
                        noti_topic = '{}'.format(urlparse(conf.conf['sub'][i]['nu']).path)

        mqtt_connect(conf.conf['cse']["host"])

        muv_mqtt_connect('localhost', 1883)


def git_clone(mission_name, directory_name, repository_url):
    try:
        shutil.rmtree('./{}'.format(directory_name))
    except Exception as e:
        print(e)

    gitClone = subprocess.Popen(['git', 'clone', repository_url, directory_name], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)

    try:
        stdout, stderr = gitClone.communicate()
        retcode = gitClone.returncode
        if retcode == 0:
            print('stdout: {}'.format(stdout))
            print('cloning finish...')
            requireMsw(mission_name, directory_name)
        else:
            print('stderr: {}'.format(stdout))
    except Exception as e:
        print("git_clone Error: ", sys.exc_info())


def git_pull(mission_name, directory_name):
    try:
        if platform.system() == 'Windows':
            cmd = 'git'
        else:
            cmd = 'git'

        gitPull = subprocess.Popen([cmd, 'pull'], stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, cwd=os.getcwd() + '/' + directory_name, text=True)

        (stdout, stderr) = gitPull.communicate()

        retcode = gitPull.returncode
        if retcode == 0:
            print('stdout: {}'.format(stdout))
            requireMsw(mission_name, directory_name)
        else:
            print('stderr: {}'.format(stdout))

    except Exception as e:
        print('git_pull Error: ', sys.exc_info())


def npm_install(mission_name, directory_name):
    print("Start npm_install")
    try:
        if platform.system() == 'Windows':
            cmd = 'npm.cmd'
        else:
            cmd = 'npm'

        npmInstall = subprocess.Popen([cmd, 'install'], stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, cwd=os.getcwd() + '/' + directory_name, text=True)

        (stdout, stderr) = npmInstall.communicate()

        retcode = npmInstall.returncode
        if retcode == 0:
            print('stdout: {}'.format(stdout))
            fork_msw(mission_name, directory_name)
        else:
            print('stderr: {}'.format(stdout))
            npm_install(mission_name, directory_name)

    except Exception as e:
        print('npm_install Error', sys.exc_info())


def fork_msw(mission_name, directory_name):
    global my_sortie_name
    global drone_info

    print('Start fork_msw')

    try:
        executable_name = directory_name + '/' + mission_name + '.js'
        dir_name = directory_name
        drone_info_gcs = drone_info["gcs"]
        drone_info_drone = drone_info["drone"]

        nodeMsw = subprocess.Popen(
            ['node', executable_name, my_sortie_name, dir_name, drone_info_gcs, drone_info_drone],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        (stdout, stderr) = nodeMsw.communicate()

        retcode = nodeMsw.returncode
        if retcode == 0:
            print('stdout: {}'.format(stdout))

        else:
            print('stderr: {}'.format(stdout))
            npm_install(mission_name, directory_name)

    except Exception as e:
        print('fork_msw Error', sys.exc_info())


msw_directory = {}


def requireMsw(mission_name, directory_name):
    global msw_package
    global msw_directory
    global drone_info
    global webrtc_room_number

    require_msw_name = directory_name.replace(mission_name + '_', '')
    msw_directory[require_msw_name] = directory_name

    if mission_name == 'msw_webrtc':
        os.system('sh ./' + directory_name + '/webrtc.sh ' + drone_info['host'] + ' ' + drone_info['drone'] + ' ' + webrtc_room_number)
    else:
        p = threading.Thread(target=fork_msw, args=(mission_name, directory_name,))
        p.start()
    # fork_msw(mission_name, directory_name)


def ae_response_action(status, res_body):
    aeid = res_body['m2m:ae']['aei']
    conf.conf['ae']['id'] = aeid

    return status, aeid


def create_cnt_all(count):
    if len(conf.conf['cnt']) == 0:
        return 2001, count
    else:
        try:
            if conf.conf['cnt'][count] is not None:
                parent = conf.conf['cnt'][count]['parent']
                rn = conf.conf['cnt'][count]['name']
                rsc, res_body, count = http_adn.crtct(parent, rn, count)
                if rsc == 5106 or rsc == 2001 or rsc == 4105:
                    count += 1
                    status, count = create_cnt_all(count)
                    return status, count
                else:
                    return 9999, count
            else:
                return 2001, count
        except Exception as e:
            # print(e)
            return 2001, count


def delete_sub_all(count):
    if len(conf.conf['sub']) == 0:
        return 2001, count
    else:
        if len(conf.conf['sub']) > count:
            target = conf.conf['sub'][count]['parent'] + '/' + conf.conf['sub'][count]['name']
            rsc, res_body, count = http_adn.delsub(target, count)
            if rsc == 5106 or rsc == 2002 or rsc == 2000 or rsc == 4105 or rsc == 4004:
                count += 1
                status, count = delete_sub_all(count)
                return status, count
            else:
                return 9999, count
        else:
            return 2001, count


def create_sub_all(count):
    if len(conf.conf['sub']) == 0:
        return 2001, count
    else:
        if len(conf.conf['sub']) > count:
            parent = conf.conf['sub'][count]['parent']
            rn = conf.conf['sub'][count]['name']
            nu = conf.conf['sub'][count]['nu']
            rsc, res_body, count = http_adn.crtsub(parent, rn, nu, count)
            if rsc == 5106 or rsc == 2001 or rsc == 4105:
                count += 1
                status, count = create_sub_all(count)
                return status, count
            else:
                return '9999', count
        else:
            return 2001, count


drone_info = {}
mission_parent = []


def retrieve_my_cnt_name():
    global drone_info
    global mission_parent
    global MQTT_SUBSCRIPTION_ENABLE
    global muv_sub_gcs_topic
    global noti_topic
    global my_system_id
    global muv_pub_fc_gpi_topic
    global muv_pub_fc_hb_topic
    global muv_sub_msw_topic
    global my_drone_type
    global my_cnt_name
    global my_parent_cnt_name
    global webrtc_room_number

    res, res_body, count = http_adn.rtvct(
        '/Mobius/' + conf.conf['ae']['approval_gcs'] + '/approval/' + conf.conf['ae']['name'] + '/la', 0)
    if res == 2000:
        drone_info = res_body['m2m:cin']['con']

        conf.conf['sub'] = []
        conf.conf['cnt'] = []
        conf.conf['fc'] = []

        my_gcs_name = drone_info["gcs"]

        if drone_info.get("host"):
            conf.conf['cse']["host"] = drone_info["host"]

        print("gcs host is " + conf.conf['cse']["host"])

        info = {}
        info['parent'] = '/Mobius/' + drone_info["gcs"]
        info['name'] = 'Drone_Data'
        conf.conf['cnt'].append(info)

        info = {}
        info['parent'] = '/Mobius/' + drone_info["gcs"] + '/Drone_Data'
        info['name'] = drone_info["drone"]
        conf.conf['cnt'].append(info)

        info = {}
        info['parent'] = '/Mobius/' + drone_info["gcs"] + '/Drone_Data/' + drone_info["drone"]
        info['name'] = my_sortie_name
        conf.conf['cnt'].append(info)

        my_parent_cnt_name = info['parent']
        my_cnt_name = my_parent_cnt_name + '/' + info['name']

        # set container for mission
        info = {}
        info['parent'] = '/Mobius/' + drone_info["gcs"]
        info['name'] = 'Mission_Data'
        conf.conf['cnt'].append(info)

        info = {}
        info['parent'] = '/Mobius/' + drone_info["gcs"] + '/Mission_Data'
        info['name'] = drone_info["drone"]
        conf.conf['cnt'].append(info)

        if drone_info.get('mission'):
            for mission_name in drone_info['mission']:
                if drone_info['mission'].get(mission_name):
                    info = {}
                    info['parent'] = '/Mobius/' + drone_info["gcs"] + '/Mission_Data/' + drone_info["drone"]
                    info['name'] = mission_name
                    if drone_info['mission'].get('msw_webrtc'):
                        pass
                    else:
                        conf.conf['cnt'].append(info)

                    chk_cnt = 'container'
                    if drone_info['mission'][mission_name].get(chk_cnt):
                        for i in range(len(drone_info['mission'][mission_name][chk_cnt])):
                            if drone_info['mission'][mission_name][chk_cnt][i] is not None:
                                container_name = drone_info['mission'][mission_name][chk_cnt][i].split(':')[0]
                                info = {}
                                info['parent'] = '/Mobius/' + drone_info["gcs"] + '/Mission_Data/' + drone_info[
                                    "drone"] + '/' + mission_name
                                info['name'] = container_name
                                if drone_info['mission'].get('msw_webrtc'):
                                    webrtc_room_number = container_name
                                else:
                                    conf.conf['cnt'].append(info)

                                info = {}
                                info['parent'] = '/Mobius/' + drone_info["gcs"] + '/Mission_Data/' + drone_info[
                                    "drone"] + '/' + mission_name + '/' + container_name
                                info['name'] = my_sortie_name
                                if drone_info['mission'].get('msw_webrtc'):
                                    pass
                                else:
                                    conf.conf['cnt'].append(info)
                                    mission_parent.append(info['parent'])
                                    muv_sub_msw_topic.append(info['parent'] + '/#')

                                if len(drone_info['mission'][mission_name][chk_cnt][i].split(':')) > 1:
                                    info = {}
                                    info['parent'] = '/Mobius/' + drone_info["gcs"] + '/Mission_Data/' + drone_info[
                                        "drone"] + '/' + mission_name + '/' + container_name
                                    info['name'] = 'sub_msw'
                                    info['nu'] = 'mqtt://' + conf.conf["cse"]["host"] + '/' + \
                                                 drone_info['mission'][mission_name][chk_cnt][i].split(':')[
                                                     1] + '?ct=json'
                                    if drone_info['mission'].get('msw_webrtc'):
                                        pass
                                    else:
                                        conf.conf['sub'].append(info)

                    chk_cnt = 'sub_container'
                    if drone_info['mission'][mission_name].get(chk_cnt):
                        for i in range(len(drone_info['mission'][mission_name][chk_cnt])):
                            if drone_info['mission'][mission_name][chk_cnt][i] is not None:
                                sub_container_name = drone_info['mission'][mission_name][chk_cnt][i]
                                info = {}
                                info['parent'] = '/Mobius/' + drone_info["gcs"] + '/Mission_Data/' + drone_info[
                                    "drone"] + '/' + mission_name
                                info['name'] = sub_container_name
                                if drone_info['mission'].get('msw_webrtc'):
                                    pass
                                else:
                                    conf.conf['cnt'].append(info)

                                info = {}
                                info['parent'] = '/Mobius/' + drone_info["gcs"] + '/Mission_Data/' + drone_info[
                                    "drone"] + '/' + mission_name + '/' + sub_container_name
                                info['name'] = 'sub_msw'
                                info['nu'] = 'mqtt://' + conf.conf["cse"]["host"] + '/' + conf.conf['ae'][
                                    'id'] + '?ct=json'
                                if drone_info['mission'].get('msw_webrtc'):
                                    pass
                                else:
                                    conf.conf['sub'].append(info)

                    chk_cnt = 'fc_container'
                    if drone_info['mission'][mission_name].get(chk_cnt):
                        for i in range(len(drone_info['mission'][mission_name][chk_cnt])):
                            if drone_info['mission'][mission_name][chk_cnt][i] is not None:
                                container_name = drone_info['mission'][mission_name][chk_cnt][i]
                                info = {}
                                info['parent'] = '/Mobius/' + drone_info["gcs"] + '/Mission_Data/' + drone_info[
                                    "drone"] + '/' + mission_name
                                info['name'] = container_name
                                if drone_info['mission'].get('msw_webrtc'):
                                    pass
                                else:
                                    conf.conf['fc'].append(info)

                    chk_cnt = 'git'
                    if drone_info['mission'][mission_name].get(chk_cnt):
                        repo_arr = drone_info['mission'][mission_name][chk_cnt].split('/')
                        directory_name = mission_name + '_' + repo_arr[len(repo_arr) - 1].replace('.git', '')
                        try:
                            if os.path.isdir('./' + directory_name):
                                git_pull(mission_name, directory_name)
                            else:
                                git_clone(mission_name, directory_name, drone_info['mission'][mission_name][chk_cnt])
                        except Exception as e:
                            print(e)

        if drone_info.get('type'):
            my_drone_type = drone_info['type']
        else:
            my_drone_type = 'pixhawk'

        drone_type = {}
        drone_type['type'] = my_drone_type
        with open('./drone_type.json', 'w') as f:
            json.dump(drone_type, f, indent=4)

        if drone_info.get('system_id'):
            my_system_id = drone_info['system_id']
        else:
            my_system_id = 8

        muv_pub_fc_gpi_topic = '/Mobius/' + my_gcs_name + '/Drone_Data/' + drone_info["drone"] + '/global_position_int'
        muv_pub_fc_hb_topic = '/Mobius/' + my_gcs_name + '/Drone_Data/' + drone_info["drone"] + '/heartbeat'

        muv_sub_gcs_topic = '/Mobius/' + my_gcs_name + '/GCS_Data/' + drone_info["drone"]
        MQTT_SUBSCRIPTION_ENABLE = 1
        thyme.sh_state = 'crtae'
        http_watchdog()
    else:
        print('x-m2m-rsc : ' + str(res) + ' <----' + str(res_body))
        time.sleep(0.25)
        http_watchdog()


def http_watchdog():
    global return_count
    global request_count

    if thyme.sh_state == 'rtvct':
        print('[sh_state] : {}'.format(thyme.sh_state))
        retrieve_my_cnt_name()
    elif thyme.sh_state == 'crtae':
        print('[sh_state] : {}'.format(thyme.sh_state))
        status, res_body = http_adn.crtae(conf.conf['ae']['parent'], conf.conf['ae']['name'], conf.conf['ae']['appid'])
        print(res_body)
        if status == 2001:
            status, aeid = ae_response_action(status, res_body)
            print('x-m2m-rsc : ' + str(status) + ' - ' + aeid + ' <----')
            thyme.sh_state = 'rtvae'
            request_count = 0
            return_count = 0

            http_watchdog()
        elif status == 5106 or status == 4105:
            print('x-m2m-rsc : ' + str(status) + ' <----')
            thyme.sh_state = 'rtvae'

            http_watchdog()
        else:
            print('x-m2m-rsc : ' + str(status) + ' <----')
            http_watchdog()
    elif thyme.sh_state == 'rtvae':
        if conf.conf['ae']['id'] == 'S':
            conf.conf['ae']['id'] = 'S' + uuid.uuid1()

        print('[sh_state] : {}'.format(thyme.sh_state))
        status, res_body = http_adn.rtvae(conf.conf['ae']['parent'] + '/' + conf.conf['ae']['name'])
        if status == 2000:
            aeid = res_body['m2m:ae']['aei']
            print('x-m2m-rsc : ' + str(status) + ' - ' + aeid + ' <----')

            if (conf.conf['ae']['id'] != aeid) and (conf.conf['ae']['id'] != ('/' + aeid)):
                print('AE-ID created is ' + aeid + ' not equal to device AE-ID is ' + conf.conf['ae']['id'])
            else:
                thyme.sh_state = 'crtct'
                request_count = 0
                return_count = 0

                http_watchdog()
        else:
            print('x-m2m-rsc : ' + str(status) + ' <----')
            http_watchdog()
    elif thyme.sh_state == 'crtct':
        print('[sh_state] : {}'.format(thyme.sh_state))
        status, count = create_cnt_all(request_count)
        if status == 9999:
            http_watchdog()
        else:
            count += 1
            request_count = count
            return_count = 0
            if len(conf.conf['cnt']) <= count:
                thyme.sh_state = 'delsub'
                request_count = 0
                return_count = 0

                http_watchdog()
    elif thyme.sh_state == 'delsub':
        print('[sh_state] : {}'.format(thyme.sh_state))
        status, count = delete_sub_all(request_count)
        if status == 9999:
            http_watchdog()
        else:
            count += 1
            request_count = count
            return_count = 0
            if len(conf.conf['sub']) <= count:
                thyme.sh_state = 'crtsub'
                request_count = 0
                return_count = 0

                http_watchdog()
    elif thyme.sh_state == 'crtsub':
        print('[sh_state] : {}'.format(thyme.sh_state))
        status, count = create_sub_all(request_count)
        if status == 9999:
            http_watchdog()
        else:
            count += 1
            request_count = count
            return_count = 0
            if len(conf.conf['sub']) <= count:
                thyme.sh_state = 'crtci'

                ready_for_notification()

                tas_mav.tas_ready()

                http_watchdog()
    elif thyme.sh_state == 'crtci':
        # print('[sh_state] : {}'.format(thyme.sh_state))
        pass


def fc_on_connect(client, userdata, flags, rc):
    global muv_sub_gcs_topic
    global noti_topic

    if muv_sub_gcs_topic != '':
        thyme.mqtt_client.subscribe(muv_sub_gcs_topic, 0)
        print('[mqtt_connect] muv_sub_gcs_topic is subscribed: ' + muv_sub_gcs_topic)

    if noti_topic != '':
        thyme.mqtt_client.subscribe(noti_topic, 0)
        print('[mqtt_connect] noti_topic is subscribed:  ' + noti_topic)


def fc_on_subscribe(client, userdata, mid, granted_qos):
    print("mqtt_client subscribed: " + str(mid) + " " + str(granted_qos))


def fc_on_message(client, userdata, msg):
    global muv_sub_gcs_topic
    global noti_topic

    if msg.topic == muv_sub_gcs_topic:
        message = tas_mav.Hex(msg.payload)
        tas_mav.gcs_noti_handler(bytearray.fromhex(" ".join(message[i:i + 2] for i in range(0, len(message), 2))))

    else:
        if '/oneM2M/req/' in msg.topic:
            jsonObj = json.loads(msg.payload)

            if not (jsonObj.get('m2m:rqp')):
                jsonObj['m2m:rqp'] = jsonObj

            noti.mqtt_noti_action(msg.topic.split('/'), jsonObj)


def fc_on_log(client, userdata, level, buf):
    print("{} {}".format(level, buf))


def mqtt_connect(serverip):
    global muv_sub_gcs_topic
    global noti_topic

    if thyme.mqtt_client is None:
        if conf.conf['usesecure'] == 'disable':
            thyme.mqtt_client = mqtt.Client(clean_session=True)
            thyme.mqtt_client.on_connect = fc_on_connect
            thyme.mqtt_client.on_subscribe = fc_on_subscribe
            thyme.mqtt_client.on_message = fc_on_message
            thyme.mqtt_client.connect(serverip, int(conf.conf['cse']['mqttport']), keepalive=10)
            thyme.mqtt_client.loop_start()
            print('fc_mqtt is connected to {}'.format(serverip))

        else:
            thyme.mqtt_client = mqtt.Client(clean_session=True)
            thyme.mqtt_client.on_connect = fc_on_connect
            thyme.mqtt_client.on_subscribe = fc_on_subscribe
            thyme.mqtt_client.on_message = fc_on_message
            thyme.mqtt_client.tls_set(certfile='./server-crt.pem', keyfile='./server-key.pem')
            thyme.mqtt_client.connect(serverip, int(conf.conf['cse']['mqttport']), keepalive=10)
            thyme.mqtt_client.loop_start()
            print('fc_mqtt is connected to {}'.format(serverip))


def muv_on_connect(client, userdata, flags, rc):
    global muv_sub_msw_topic

    for idx in range(len(muv_sub_msw_topic)):
        thyme.muv_mqtt_client.subscribe(muv_sub_msw_topic[idx], 0)
        print('[muv_mqtt_connect] noti_topic[{0}]: {1}'.format(str(idx), muv_sub_msw_topic[idx]))


def muv_on_subscribe(client, userdata, mid, granted_qos):
    print("muv_sub_msw_topic subscribed: " + str(mid) + " " + str(granted_qos))


def muv_on_message(client, userdata, msg):
    message = str(msg.payload.decode("utf-8"))

    try:
        msg_obj = json.loads(message)
        print(msg_obj)
        send_to_Mobius(msg.topic, msg_obj, int(random.random() * 10))

    except Exception as e:
        msg_obj = message
        send_to_Mobius(msg.topic, msg_obj, int(random.random() * 10))
        # print(topic + ' - ' + msg_obj)


def muv_mqtt_connect(broker_ip, port):
    global muv_sub_msw_topic

    if thyme.muv_mqtt_client is None:
        if conf.conf['usesecure'] == 'disable':
            thyme.muv_mqtt_client = mqtt.Client(clean_session=True)
            thyme.muv_mqtt_client.on_connect = muv_on_connect
            thyme.muv_mqtt_client.on_subscribe = muv_on_subscribe
            thyme.muv_mqtt_client.on_message = muv_on_message
            thyme.muv_mqtt_client.connect(broker_ip, port, keepalive=10)
            thyme.muv_mqtt_client.loop_start()
            print('muv_mqtt_client connected to {}'.format(broker_ip))

        else:
            thyme.muv_mqtt_client = mqtt.Client(clean_session=True)
            thyme.muv_mqtt_client.on_connect = muv_on_connect
            thyme.muv_mqtt_client.on_subscribe = muv_on_subscribe
            thyme.muv_mqtt_client.on_message = muv_on_message
            thyme.muv_mqtt_client.tls_set(certfile='./server-crt.pem', keyfile='./server-key.pem')
            thyme.muv_mqtt_client.connect(broker_ip, port, keepalive=10)
            thyme.muv_mqtt_client.loop_start()
            print('muv_mqtt_client connected to {}'.format(broker_ip))


def send_to_Mobius(topic, content_each_obj, gap):
    http_adn.crtci(topic + '?rcn=0', 0, content_each_obj, None)
