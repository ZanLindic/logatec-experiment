#!/usr/bin/python3
import threading
from queue import Queue

import sys
import os
import logging
import time
from subprocess import Popen, PIPE

from lib import zmq_client

class zmq_client_thread(threading.Thread):

    # ----------------------------------------------------------------------------------------
    # INIT
    # ----------------------------------------------------------------------------------------
    def __init__(self, input_q, output_q, lgtc_id, subscriber, router):

        threading.Thread.__init__(self)
        self._is_thread_running = True

        self.in_q = input_q
        self.out_q = output_q

        self.client = zmq_client.zmq_client(subscriber, router, lgtc_id)
        self.__LGTC_STATE = "OFFLINE"


    # ----------------------------------------------------------------------------------------
    # MAIN
    # ----------------------------------------------------------------------------------------
    def run(self):

        # Sync with broker with timeout of 10 seconds
        logging.info("Sync with broker ... ")
        self.client.transmit(["-1", "SYNC"])
        if self.client.wait_ack("-1", 10) is False:
            logging.error("Couldn't synchronize with broker...")
            # TODO: Continue application without broker?
        

        # ------------------------------------------------------------------------------------
        while self._is_thread_running:

            # If there is a message from VESNA
            # --------------------------------------------------------------------------------
            if not self.in_q.empty():
                logging.debug("Got message from VESNA")
                response = self.in_q.get()
                
                # If the message is SYSTEM - application controll
                if response[0] == "-1":
                    if response[1] == "START_APP":
                        self.LGTC_set_state("RUNNING")

                    elif response[1] == "STOP_APP":
                        self.LGTC_set_state("STOPPED")
                    
                    elif response[1] == "SYNCED_WITH_VESNA":
                        self.LGTC_set_state("ONLINE")

                    elif response[1] == "END_OF_APP":
                        self.LGTC_set_state("FINISHED")

                    elif response[1] == "VESNA_TIMEOUT":
                        self.LGTC_set_state("TIMEOUT")

                    elif response[1] == "VESNA_ERR":
                        self.LGTC_exit("VESNA_ERROR")
                        break
                    
                    else:
                        self.LGTC_set_state("LGTC_WARNING")
                        logging.debug("Unsupported state")                    
                
                # If the message is CMD - experiment response
                else:
                    self.client.transmit_async(response)
            
            # --------------------------------------------------------------------------------
            # If there is some incoming commad from the broker
            inp = self.client.check_input(0)
            if inp:
                msg_nbr, msg = self.client.receive_async(inp)

                # If the message is not ACK
                if msg_nbr:

                    logging.info("Received " + msg + " command!")
                    # SYSTEM COMMANDS - application controll
                    if msg_nbr == "-1":

                        if msg == "EXIT":
                            logging.info("Closing the app.")
                            break

                        elif msg == "STATE":
                            self.client.transmit_async(["-1", self.LGTC_get_state()])
                            
                        elif msg == "FLASH":
                            logging.info("Compile the application ... ")
                            self.LGTC_set_state("COMPILING")
                            if not self.LGTC_flash_vesna():
                                self.LGTC_exit("COMPILE_ERROR")
                                break

                        elif msg == "RESTART_APP":
                            # TODO: Store measurements under a different filename?
                            self.out_q.put(["-1", "STOP_APP"])
                            time.sleep(1)   # Wait a little?
                            self.LGTC_reset_vesna()
                            self.out_q.put(["-1", "START_APP"])

                        elif msg == "START_APP":
                            self.out_q.put([msg_nbr, msg])

                        elif msg == "STOP_APP":
                            self.out_q.put([msg_nbr, msg])
                        
                        else:
                            self.LGTC_set_state("LGTC_WARNING")
                            logging.warning("Unsupported command!")


                    # EXPERIMENT COMMANDS - experiment command
                    else:
                        self.out_q.put([msg_nbr, msg])


            # --------------------------------------------------------------------------------
            # If there is still some message that didn't receive ACK back from server, re send it
            elif (len(self.client.waitingForAck) != 0):
                self.client.send_retry()

        # ------------------------------------------------------------------------------------
        logging.debug("Exiting client thread")
        #self.client.close()


    # ----------------------------------------------------------------------------------------
    # END
    # ----------------------------------------------------------------------------------------
    def stop(self):
        self._is_thread_running = False

    


    # ----------------------------------------------------------------------------------------
    # OTHER FUNCTIONS
    # ----------------------------------------------------------------------------------------

    # Use in case of fatal errors in experiment app
    def LGTC_exit(self, reason):
        self.client.transmit(["-1", reason])
        if self.client.wait_ack("-1", 3):
            return True
        else:
            logging.warning("No ACK from server while exiting...force exit.")
            return False

    # Get global variable
    def LGTC_get_state(self):
        return self.__LGTC_STATE

    # Set global variable
    def LGTC_set_state(self, state):
        self.__LGTC_STATE = state
        # Send new state to the server (WARNING: async method used...)
        self.client.transmit_async(["-1", state])

    # Compile the C app and VESNA with its binary
    def LGTC_flash_vesna(self):
        # Compile the application
        procCompile = Popen(["make", APP_NAME, "-j2"], stdout = PIPE, stderr= PIPE, cwd = APP_PATH)
        stdout, stderr = procCompile.communicate()
        logging.debug(stdout)
        if(stderr):
            logging.debug(stderr)
            return False

        # Flash the VESNA with app binary
        logging.info("Flash the app to VESNA .. ")
        procFlash = Popen(["make", APP_NAME + ".logatec3"], stdout = PIPE, stderr= PIPE, cwd = APP_PATH)
        stdout, stderr = procFlash.communicate()
        logging.debug(stdout)
        if(stderr):
            logging.debug(stderr)
            return False

        return True

    # Make a hardware reset on VESNA
    def LGTC_reset_vesna(self):
        try:
            os.system('echo 66 > /sys/class/gpio/export')
        except Exception:
            pass
        os.system('echo out > /sys/class/gpio/gpio66/direction')

        os.system('echo 0 > /sys/class/gpio/gpio66/value')
        os.system('echo 1 > /sys/class/gpio/gpio66/value')



# ----------------------------------------------------------------------------------------
# POSSIBLE LGTC STATES
# ----------------------------------------------------------------------------------------
# --> ONLINE        - LGTC is online and ready
# --> COMPILING     - LGTC is compiling the experiment application
# --> RUNNING       - Experiment application is running
# --> STOPPED       - User successfully stopped the experiment app
# --> FINISHED      - Experiment application came to the end
#
# --> TIMEOUT       - VESNA is not responding for more than a minute
# --> LGTC_WARNING  - Warning sign that something was not as expected
# --> COMPILE_ERROR - Experiment application could not be compiled
# --> VESNA_ERROR   - Problems with UART communication
#
#
# ----------------------------------------------------------------------------------------
# SUPPORTED COMMANDS
# ----------------------------------------------------------------------------------------
# Incoming commands must be formated as a list with 2 string arguments: message number 
# and command itself (example: ["66", "STATE"]). Message number is used as a sequence
# number, but if it is set to "-1", command represents SYSTEM COMMAND:
#
# --> SYSTEM COMMANDS - used for controll over the LGTC monitoring application
#
#       * START_APP       - start the experiment application
#       * STOP_APP        -
#       * RESTART_APP     - 
#       * FLASH           - flash VESNA with experiment application
#       * SYNC_WITH_VESNA - start the serial monitor
#       * EXIT            - exit monitoring application
#       * STATE           - return the current state of monitoring application
#       * SYNC            - used to synchronize LGTC with broker/server
#       * ACK             - acknowledge packet sent as a response on every message
#       
# --> EXPERIMENT COMMANDS - used for controll over the VESNA experiment application
#
#       * LINES           - return the number of lines stored in measurement file
#       * SEC             - return the number of elapsed seconds since the beginning of exp.
#       TODO:
#       They should start with the char "*" so VESNA will know?
#       Depend on Contiki-NG application
#