/*
 * View model for OctoPrint-Mtcadapter
 *
 * Author: Jorge E Correa
 * License: AGPLv3
 */
$(function() {
    function MtcadapterViewModel(parameters) {
        var self = this;

        // assign the injected parameters
        self.settings = parameters[0];

        // modal dialogs
        self.connect_server = undefined;
        self.disconnect_server = undefined;

        // state variables
        self.running = false;

        // events
        self.onAfterBinding = function() {
            // bind to modals
            self.connect_server = $("#connect_server");
            self.disconnect_server = $("#disconnect_server");

            // start alerts
            $("#success-start").hide();
            $("#failure-start").hide();
            $("#success-stop").hide();
            $("#failure-stop").hide();
        };

        self.changeServerStatus = function () {
            if (!self.running)
                self.connect_server.modal("show");
            else
                self.disconnect_server.modal("show");
        };

        // API calls
        self.startServer = function () {
            $.ajax({
                 url: API_BASEURL + "plugin/mtcadapter",
                 type: "POST",
                 dataType: "json",
                 data: JSON.stringify({
                     command: "start"
                 }),
                 contentType: "application/json; charset=UTF-8",
                 success: function (data,status) {
                 self.running = true;
                    if (data.success){
                        // Notify the user
                        $("#success-start").fadeTo(2000, 500).slideUp(500, function(){
                            $("#success-start").slideUp(500);
                        });
                    }
                    else {
                         // Notify the user
                         $("#failure-start").fadeTo(2000, 500).slideUp(500, function(){
                            $("#failure-start").slideUp(500);
                         })
                    }
                 },
                 error: function (err){
                    // Notify the user
                    $("#failure-start").fadeTo(2000, 500).slideUp(500, function(){
                       $("#failure-start").slideUp(500);
                    })
                    // notify the developer
                    console.log(err);
                 },
            });
            self.connect_server.modal("hide");
        }

        self.stopServer = function () {
            $.ajax({
                 url: API_BASEURL + "plugin/mtcadapter",
                 type: "POST",
                 dataType: "json",
                 data: JSON.stringify({
                     command: "stop"
                 }),
                 contentType: "application/json; charset=UTF-8",
                 success: function (data,status) {
                 self.running = false;
                    if (data.success){
                        // Notify the user
                        $("#success-stop").fadeTo(2000, 500).slideUp(500, function(){
                            $("#success-stop").slideUp(500);
                        });
                    }
                    else {
                         // Notify the user
                         $("#failure-stop").fadeTo(2000, 500).slideUp(500, function(){
                            $("#failure-stop").slideUp(500);
                         })
                    }
                 },
                 error: function (err){
                    // Notify the user
                    $("#failure-stop").fadeTo(2000, 500).slideUp(500, function(){
                       $("#failure-stop").slideUp(500);
                    })
                    // notify the developer
                    console.log(err);
                 },
            });
            self.disconnect_server.modal("hide");
        }

    }

    /* view model class, parameters for constructor, container to bind to
     * Please see http://docs.octoprint.org/en/master/plugins/viewmodels.html#registering-custom-viewmodels for more details
     * and a full list of the available options.
     */
    OCTOPRINT_VIEWMODELS.push({
        construct: MtcadapterViewModel,
        // ViewModels your plugin depends on, e.g. loginStateViewModel, settingsViewModel, ...
        dependencies: [ "settingsViewModel" ],
        // Elements to bind to, e.g. #settings_plugin_mtcadapter, #tab_plugin_mtcadapter, ...
        elements: [ "#navbar_plugin_mtcadapter",  "#settings_plugin_mtcadapter"]
    });
});
