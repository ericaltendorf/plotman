#!/bin/sh

. ${PLOTMAN_HOOKS}/.lib.include

[ "${PLOTMAN_TRIGGER}" = "PHASE" ] || exit 0

[ x"${PLOTMAN_PHASE}" = x0:0 ] || exit 0

logInfo "New plotter process with pid: ${PLOTMAN_PID}, id: ${PLOTMAN_PLOTID} was just started"
