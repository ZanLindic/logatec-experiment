/* ----------------------------------------------------------------------------
 * NOISE GENERATION - AT86RF231 CONTINUOUS TRANSMISSION TEST MODE 
 * 
 * You must enter the application duration here (and in serial_monitor.py)
 * ----------------------------------------------------------------------------
*/
#include <stdio.h>
#include "contiki.h"
#include "../../contiki-ng/arch/platform/vesna/dev/at86rf2xx/rf2xx.h"
#include "../../vesna-drivers/VESNALib/inc/vsntime.h" // For delayS

/*---------------------------------------------------------------------------*/
#define APP_DURATION_IN_SEC    (60 * 60)

/*---------------------------------------------------------------------------*/
PROCESS(continuous_transmission_test_mode_process, "CTTM process");
AUTOSTART_PROCESSES(&continuous_transmission_test_mode_process);

/*---------------------------------------------------------------------------*/
PROCESS_THREAD(continuous_transmission_test_mode_process, ev, data){

    static struct etimer timer;

    PROCESS_BEGIN();

    printf("Set radio to: continuos transmission test mode. \n");
    rf2xx_CTTM_start();

    vsnTime_delayS(APP_DURATION_IN_SEC);

    rf2xx_CTTM_stop();
    printf("Stop continuos transmission test mode. \n");

    while(1){}

    /* Setup a periodic timer that expires after 10 seconds. */
    etimer_set(&timer, CLOCK_SECOND * 10);

    while(1) {

        printf("Main loop \n");

        /* Wait for the periodic timer to expire and then restart the timer. */
        PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&timer));
        etimer_reset(&timer);
    }

    PROCESS_END();
}