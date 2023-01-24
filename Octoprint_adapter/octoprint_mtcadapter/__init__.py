#
# /**************************************************
# * MTconnect adapter plugin for Cctoprint.         *
# *                                                 *
# * Jorge Correa                                    *
# * Placid Ferreira                                 *
# *                                                 *
# * University of Illinois at urbana champaign      *
# * fall 2017                                       *
# *                                                 *
# * DMDII project: Operating System for             *
# * Cyberphysical Manufacturing                     *
# *                                                 *
# ***************************************************/

# /*
# * An MTConnect adapter plugin for Octorprint that user can use to connect their 3D printer to OSCM
# *
# * References:
# * Octoprint Hooks. octoprint.comm.protocol.gcode.received: http://docs.octoprint.org/en/master/plugins/hooks.html#octoprint-comm-protocol-gcode-received
# * Octoprint.Event handler. Available events: http://docs.octoprint.org/en/master/events/index.html#sec-events-available-events
# */

# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
import socket
from threading import Thread
import flask
import time
import datetime
import sys
import json


class MtcadapterPlugin(octoprint.plugin.StartupPlugin,    # a mixin (base class) plugging for  hooking into the startup of OctoPrint.
                       # allows users to customized the behaviour of your plugin
                       octoprint.plugin.SettingsPlugin,
                       # allows plugins to define additional static assets such as JavaScript or CSS files
                       octoprint.plugin.AssetPlugin,
                       # inject mixing pluging components into the OctoPrint web interface.
                       octoprint.plugin.TemplatePlugin,
                       octoprint.plugin.SimpleApiPlugin):  # implement a simple API based around one GET resource and one POST resource
    # ~~ MtcadapterPlugin private variables
    def __init__(self):
        # ~~ TCP socket initialization
        self.ip = '127.0.0.1'
        self.port = 7171

        # ~~ server thread initialization
        self.is_serving = False
        self.update_delay = 1  # time interterval to request a position update
        self.comm_delay = 1  # time interval to send a posotion update to the printer

        # ~~ machine state vector
        self.state = {}

        # ~~ position state
        self.unit = 'mm'  # default to millimeter as unit
        self.positioning_mode = 'abs'  # default to absolute positioning mode
        self.extrusion_mode = 'abs'  # default to absolute extrusion mode
        self.stored_pos = {'xpos': 0.,
                           'ypos': 0.,
                           'zpos': 0.,
                           'epos': 0.}

    # ~~ Startup mixing
    def on_after_startup(self):
        self._logger.info("Hello MTConnect Adapter!. IP address: %s:%s", self._settings.get(
            ["ip"]), int(self._settings.get(["port"])))  # logger and

    # ~~ SettingsPlugin mixin
    def get_settings_defaults(self):
        return dict(
            # put your plugin's default settings here
            ip=self.ip,
            port=self.port,
            comm_delay=self.comm_delay,
            update_delay=self.update_delay
        )

    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings=False)
        ]

    # ~~ SimpleApiPlugin mixin
    def get_api_commands(self):
        return dict(
            start=[],
            stop=[]
        )

    def on_api_command(self, command, data):
        # notified the user
        self._logger.info(
            "API command \"{command}\" received".format(**locals()))

        if command == "start":
            # check that the server is not already started
            if self.is_serving:
                self._logger.info("Error: Server already started")
                return flask.jsonify(success=False)

            # start the socket thread
            self.is_serving = True
            t = Thread(target=self.thread_server)
            t.start()

            # return
            return flask.jsonify(success=True)

        if command == "stop":
            # check that the server is running
            if not self.is_serving:
                return flask.jsonify(success=False)

            # stop the socket thread
            self.is_serving = False
            # return
            return flask.jsonify(success=True)

    # ~~ AssetPlugin mixin
    def get_assets(self):
        # Define your plugin's asset files to automatically include in the
        # core UI here.
        return dict(
            js=["js/mtcadapter.js"],
            css=["css/mtcadapter.css"],
            less=["less/mtcadapter.less"]
        )

    # ~~ Softwareupdate hook
    def get_update_information(self):
        # Define the configuration for your plugin to use with the Software Update
        # Plugin here. See https://github.com/foosel/OctoPrint/wiki/Plugin:-Software-Update
        # for details.
        return dict(
            mtcadapter=dict(
                displayName="Mtcadapter Plugin",
                displayVersion=self._plugin_version,

                # version check: github repository
                type="github_release",
                user="jcorre20",
                repo="OctoPrint-Mtcadapter",
                current=self._plugin_version,

                # update method: pip
                pip="https://github.com/jcorre20/OctoPrint-Mtcadapter/archive/{target_version}.zip"
            )
        )

    # ~~ gcode phase hook (sent)
    def update_internal_state(self, comm_instance, phase, cmd, cmd_type, gcode, *args, **kwargs):
        from octoprint.util.gcodeInterpreter import getCodeFloat

        if not gcode:
            return

        # Get sent axis positions if possible
        xpos = getCodeFloat(cmd, 'X')
        ypos = getCodeFloat(cmd, 'Y')
        zpos = getCodeFloat(cmd, 'Z')
        epos = getCodeFloat(cmd, 'E')

        # Movement and position commands
        if gcode in ['G0', 'G1']:
            # Update stored axis position if possible
            if self.positioning_mode == 'abs':
                self.stored_pos['xpos'] = xpos if xpos else self.stored_pos['xpos']
                self.stored_pos['ypos'] = ypos if ypos else self.stored_pos['ypos']
                self.stored_pos['zpos'] = zpos if zpos else self.stored_pos['zpos']
            elif self.positioning_mode == 'rel':
                self.stored_pos['xpos'] = self.stored_pos['xpos'] + \
                    xpos if xpos else self.stored_pos['xpos']
                self.stored_pos['ypos'] = self.stored_pos['ypos'] + \
                    ypos if ypos else self.stored_pos['ypos']
                self.stored_pos['zpos'] = self.stored_pos['zpos'] + \
                    zpos if zpos else self.stored_pos['zpos']

            # Update stored extruder position
            if self.extrusion_mode == 'abs':
                self.stored_pos['epos'] = epos if epos else self.stored_pos['epos']
            elif self.extrusion_mode == 'rel':
                self.stored_pos['epos'] = self.stored_pos['epos'] + \
                    epos if epos else self.stored_pos['epos']

        # Change of unit type commands
        elif gcode in ['G20', 'G21']:
            if gcode == 'G20':
                self.unit = 'inch'
            elif gcode == 'G21':
                self.unit = 'mm'

        # Move to origin
        elif gcode == 'G28':
            self.stored_pos['xpos'] = 0 if 'X' in cmd else self.stored_pos['xpos']
            self.stored_pos['ypos'] = 0 if 'Y' in cmd else self.stored_pos['ypos']
            self.stored_pos['zpos'] = 0 if 'Z' in cmd else self.stored_pos['zpos']
            self.stored_pos['epos'] = 0 if 'E' in cmd else self.stored_pos['epos']

        # Change of positioning type commands
        elif gcode in ['G90', 'G91']:
            if gcode == 'G90':
                self.positioning_mode = 'abs'
            elif gcode == 'G91':
                self.positioning_mode = 'rel'

        elif gcode == 'G92':
            # Update stored position if possible
            self.stored_pos['xpos'] = xpos if xpos else self.stored_pos['xpos']
            self.stored_pos['ypos'] = ypos if ypos else self.stored_pos['ypos']
            self.stored_pos['zpos'] = zpos if zpos else self.stored_pos['zpos']
            self.stored_pos['epos'] = epos if epos else self.stored_pos['epos']

        # Set extruder positioning type commands
        elif gcode in ['M82', 'M83']:
            if gcode == 'M82':
                self.extrusion_mode = 'abs'
            elif gcode == 'M83':
                self.extrusion_mode = 'rel'

        # Update the current state of the printer
        try:
            state = self.parse_printer_data()
        except:
            return
        self.state = state

        # Update internal state (to be sent to cloud)
        self.state['xpos'] = self.stored_pos['xpos']
        self.state['ypos'] = self.stored_pos['ypos']
        self.state['zpos'] = self.stored_pos['zpos']
        self.state['epos'] = self.stored_pos['epos']

        #self._logger.info("Here is the state:")
        # self._logger.info(state)

        # Return nothing to not modify the gcode
        return

    # ~~ Class utilities
    def parse_printer_data(self):
        printer_data = self._printer.get_current_data()
        printer_temperatures = self._printer.get_current_temperatures()

        #self._logger.info("printer temperatures: {printer_temperatures}".format(**locals()))

        # initialize state
        state = {}

        # temperatures
        state['bedActualTemp'] = printer_temperatures['bed']['actual']
        state['bedTargetTemp'] = printer_temperatures['bed']['target']
        state['toolActualTemp'] = printer_temperatures['tool0']['actual']
        state['toolsTargetTemp'] = printer_temperatures['tool0']['target']

        # progress
        state['completion'] = printer_data['progress']['completion']
        state['filepos'] = printer_data['progress']['filepos']
        state['printTime'] = printer_data['progress']['printTime']
        state['printTimeLeft'] = printer_data['progress']['printTimeLeft']
        #state['printTimeOrigin'] = printer_data['progress']['printTimeOrigin']

        # state
        state['text'] = printer_data['state']['text']
        # state - flags
        state['flags'] = printer_data['state']['flags']['cancelling']
        state['paused'] = printer_data['state']['flags']['paused']
        state['operational'] = printer_data['state']['flags']['operational']
        state['pausing'] = printer_data['state']['flags']['pausing']
        state['printing'] = printer_data['state']['flags']['printing']
        #state['resuming'] = printer_data['state']['flags']['resuming']
        state['sdReady'] = printer_data['state']['flags']['sdReady']
        state['error'] = printer_data['state']['flags']['error']
        state['ready'] = printer_data['state']['flags']['ready']
        #state['finishing'] = printer_data['state']['flags']['finishing']
        state['closedOrError'] = printer_data['state']['flags']['closedOrError']

        # job
        state['estimatedPrintTime'] = printer_data['job']['estimatedPrintTime']
        #state['user'] = printer_data['job']['user']
        state['lastPrintTime'] = printer_data['job']['lastPrintTime']
        # job-file
        state['filedate'] = printer_data['job']['file']['date']
        state['fileorigin'] = printer_data['job']['file']['origin']
        state['filesize'] = printer_data['job']['file']['size']
        state['filename'] = printer_data['job']['file']['name']
        state['filepath'] = printer_data['job']['file']['path']
        # job-filament
        #state['filamentvolume'] = printer_data['job']['filament']['volume']
        #state['filamentlength'] = printer_data['job']['filament']['length']

        return state

    def printer_to_mtc(self):
        # time in UTC format YYYY-MM-DDTHH:MM:SS.FFFZ
        now = datetime.datetime.now()
        _formated_time = now.strftime('%Y-%m-%d %H:%M:%S:%fZ')

        # mtc string
        result = _formated_time

        self._logger.info("result: {result}".format(**locals()))

        if self.state['xpos'] is not None:
            result += "|xpos|" + str(self.state['xpos'])

        if self.state['ypos'] is not None:
            result += "|ypos|" + str(self.state['ypos'])

        if self.state['zpos'] is not None:
            result += "|zpos|" + str(self.state['zpos'])

        if self.state['epos'] is not None:
            result += "|epos|" + str(self.state['epos'])

        if self.state['bedActualTemp'] is not None:
            result += "|bedActualTemp|" + str(self.state['bedActualTemp'])

        if self.state['bedTargetTemp'] is not None:
            result += "|bedTargetTemp|" + str(self.state['bedTargetTemp'])

        if self.state['toolActualTemp'] is not None:
            result += "|toolActualTemp|" + str(self.state['toolActualTemp'])

        if self.state['toolsTargetTemp'] is not None:
            result += "|toolsTargetTemp|" + str(self.state['toolsTargetTemp'])

        if self.state['completion'] is not None:
            result += "|completion|" + str(self.state['completion'])

        if self.state['filepos'] is not None:
            result += "|filepos|" + str(self.state['filepos'])

        if self.state['printTime'] is not None:
            result += "|printTime|" + str(self.state['printTime'])

        if self.state['printTimeLeft'] is not None:
            result += "|printTimeLeft|" + str(self.state['printTimeLeft'])

        if self.state['text'] is not None:
            result += "|text|" + str(self.state['text'])

        if self.state['flags'] is not None:
            result += "|flags|" + str(self.state['flags'])

        if self.state['paused'] is not None:
            result += "|paused|" + str(self.state['paused'])

        if self.state['operational'] is not None:
            result += "|operational|" + str(self.state['operational'])

        if self.state['pausing'] is not None:
            result += "|pausing|" + str(self.state['pausing'])

        if self.state['printing'] is not None:
            result += "|printing|" + str(self.state['printing'])

        # if self.state['resuming'] is not None:
        #   result += "|resuming|" + str(self.state['resuming'])

        if self.state['sdReady'] is not None:
            result += "|sdReady|" + str(self.state['sdReady'])

        if self.state['error'] is not None:
            result += "|error|" + str(self.state['error'])

        if self.state['ready'] is not None:
            result += "|ready|" + str(self.state['ready'])

        # if self.state['finishing'] is not None:
        #   result += "|finishing|" + str(self.state['finishing'])

        if self.state['closedOrError'] is not None:
            result += "|closedOrError|" + str(self.state['closedOrError'])

        if self.state['estimatedPrintTime'] is not None:
            result += "|estimatedPrintTime|" + \
                str(self.state['estimatedPrintTime'])

        # if self.state['user'] is not None:
        #   result += "|user|" + str(self.state['user'])

        if self.state['lastPrintTime'] is not None:
            result += "|lastPrintTime|" + str(self.state['lastPrintTime'])

        if self.state['filedate'] is not None:
            result += "|filedate|" + str(self.state['filedate'])

        if self.state['fileorigin'] is not None:
            result += "|fileorigin|" + str(self.state['fileorigin'])

        if self.state['filesize'] is not None:
            result += "|filesize|" + str(self.state['filesize'])

        if self.state['filename'] is not None:
            result += "|filename|" + str(self.state['filename'])

        if self.state['filepath'] is not None:
            result += "|filepath|" + str(self.state['filepath'])

        return result

    def _json_encode(self, obj, encoding):
        return json.dumps(obj, ensure_ascii=False).encode(encoding)

    def _create_message(
        self, *, content_bytes, content_type, content_encoding
    ):
        jsonheader = {
            "byteorder": sys.byteorder,
            "content-type": content_type,
            "content-encoding": content_encoding,
            "content-length": len(content_bytes),
        }
        jsonheader_bytes = self._json_encode(jsonheader, "utf-8")
        message_hdr = hex(len(jsonheader_bytes)).encode("utf-8")
        message = message_hdr + jsonheader_bytes + content_bytes
        return message

    def getOSCMstring(self, msg):
        content_encoding = "utf-8"
        response = {
            "content_bytes": self._json_encode({"respond": msg}, content_encoding),
            "content_type": "text/json",
            "content_encoding": content_encoding,
        }

        return self._create_message(**response)

    def on_new_client(self, clientsocket, addr):
        self._logger.info("New client connected: {addr}".format(**locals()))
        mtc_str = ""
        while self.is_serving:
            # generate stream
            try:
                mtc_str = self.printer_to_mtc()
            except Exception as e:
                print(e)

            # send to client
            try:
                # add header to the msg
                message = self.getOSCMstring(self.state)
                # Clean buffer read
                data_in = clientsocket.recv(4096)
                # send msg
                clientsocket.send(message)
                self._logger.info(
                    "MTConnect adapter send: {message}".format(**locals()))
            except socket.error:
                self._logger.info(
                    "Client:{addr} disconnected".format(**locals()))
                break
            time.sleep(float(self._settings.get(["comm_delay"])))  # wait

        clientsocket.close()

    def thread_server(self):
        # bins socket to the current port in settings
        #ip = '192.168.1.68'
        ip = str(self._settings.get(["ip"]))
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((ip, int(self._settings.get(["port"]))))
        s.listen(1)
        self._logger.info(
            " MTConnect Adapter: Socket listing at ip: {ip}".format(**locals()))

        # wait for client connections
        while self.is_serving:
            try:
                conn, addr = s.accept()
                tc = Thread(target=self.on_new_client, args=(conn, addr))
                tc.start()
            except socket.timeout:
                pass
        # close socket
        s.close()


# If you want your plugin to be registered within OctoPrint under a different name than what you defined in setup.py
# ("OctoPrint-PluginSkeleton"), you may define that here. Same goes for the other metadata derived from setup.py that
# can be overwritten via __plugin_xyz__ control properties. See the documentation for that.
__plugin_name__ = "Mtcadapter Plugin"
__plugin_pythoncompat__ = ">=3,<4"  # Only Python 3


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = MtcadapterPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
        "octoprint.comm.protocol.gcode.sent": __plugin_implementation__.update_internal_state
    }
