# Maintenance

## Overview

This document holds guidance on maintaining aspects of plotman.

## The `chia plots create` CLI parsing code

In [src/plotman/chia.py](src/plotman/chia.py) there is code copied from the `chia plots create` subcommand's CLI parser definition.
When new versions of `chia-blockchain` are released, their interface code should be added to plotman.
plotman commit [1b5db4e](https://github.com/ericaltendorf/plotman/commit/1b5db4e342b9ec1f7910663a453aec3a97ba51a6) provides an example of adding a new version.

In many cases, copying code is a poor choice.
It is believed that in this case it is appropriate since the chia code that plotman could import is not necessarily the code that is parsing the plotting process command lines anyways.
The chia command could come from another Python environment, a system package, a `.dmg`, etc.
This approach also offers future potential of using the proper version of parsing for the specific plot process being inspected.
Finally, this alleviates dealing with the dependency on the `chia-blockchain` package.
In generally, using dependencies is good.
This seems to be an exceptional case.
