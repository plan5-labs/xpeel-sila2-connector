# xpeel-sila2-connector

A SiLA 2 connector, built on the [UniteLabs CDK](https://gitlab.com/unitelabs/cdk/python-cdk), for the Xpeel automated plate seal remover (now sold as the Automated Plate Seal Remover by Azenta Life Sciences, model XP-A_100V).

It is a port of [plan5-labs/xpeel-sila2](https://github.com/plan5-labs/xpeel-sila2) to the UniteLabs CDK. The SiLA interface is unchanged: the feature `org.riken/instruments/AutomatedPlateSealRemoverController/v1` keeps every command, parameter, response, error and property identifier, so existing clients keep working. The test suite checks this against the original feature definition.

## Features

The connector serves these SiLA features:

| Feature | Purpose |
| -- | -- |
| `AutomatedPlateSealRemoverController` | Controls the instrument. See below. |
| `SimulationController` | Switches between the instrument (Real Mode) and a simulated instrument (Simulation Mode). |
| `LockController` | Lets a client lock the connector for exclusive use. |
| `SiLAService`, `ConnectionConfigurationService` | Standard SiLA features, added by the CDK. |

`AutomatedPlateSealRemoverController` provides:

* Commands (all observable)
  * `Peel`
  * `GetTapeLeft`
  * `ResetInstrument`
  * `Reset`
* Property (observable)
  * `Status`

### Peel

Peel the seal attached to the plate.

| Parameter | Type | Description |
| -- | -- | -- |
| `BeginPeelLocation` | Integer, 1 to 9 | Beginning location and peeling speed.<br>1: Default -2 mm / fast<br>2: Default -2 mm / slow<br>3: Default / fast<br>4: Default / slow<br>5: Default +2 mm / fast<br>6: Default +2 mm / slow<br>7: Default +4 mm / fast<br>8: Default +4 mm / slow<br>9: custom / custom |
| `AdhesionTime` | Integer, 1 to 4 | Adhesion time between the peeler and the seal.<br>1: 2.5 seconds<br>2: 5.0 seconds<br>3: 7.5 seconds<br>4: 10.0 seconds |

| Response | Type | Description |
| -- | -- | -- |
| `InstrumentWarningMessage` | String | The warning for the latest warning code the instrument returned (tape running low), or an empty string if there was none. |

Requires the status Idle. The status is Running while the seal is peeled, then Idle, or Error if the command fails.

Depending on the plate and the parameters, the instrument may return an error even if the seal was removed. Try different parameters to find a combination that the instrument recognizes correctly.

### GetTapeLeft

Get the amount of tape left on the supply spool and the available capacity on the take-up spool.

| Response | Type | Description |
| -- | -- | -- |
| `SupplySpoolRemaining` | Integer | The number of seal removals remaining on the supply spool. |
| `TakeUpSpoolRemaining` | Integer | The number of seal removals that the remaining space on the take-up spool can accommodate. |
| `InstrumentWarningMessage` | String | As for `Peel`. |

Requires the status Idle and leaves it unchanged, or sets Error if the command fails. The current firmware has a bug that can make the instrument return an unexpected value for this command.

### ResetInstrument

Move the spool forward a few inches to access fresh tape, return the elevator and conveyor to their home positions, and prepare the plate for pickup. Error codes and the tape left are preserved.

Responds with `InstrumentWarningMessage`. Requires the status Idle. The status is Running until the instrument is home, then Idle, or Error if the command fails.

### Reset

Reset the server to its Idle state by restarting the instrument, which then returns to its home position. This command is common to all instruments and is how you recover from the Error status.

Responds with `InstrumentWarningMessage`. Requires the status Idle or Error, keeps it while running, and sets Idle once the instrument has restarted, or Error if it fails.

### Status

The status of the instrument. This property is common to all instruments.

| Value | Status |
| -- | -- |
| 0 | Not Connected |
| 1 | Idle |
| 2 | Running |
| 3 | Error |

The status is Not Connected whenever the connection to the instrument is down. When the serial connection drops, the connector tries to reconnect every 20 seconds and gives up after a few failed attempts; then restart the connector. A command that fails because of the dropped connection leaves the status at Error once the connector has reconnected.

### Errors

Every command can raise these defined execution errors:

| Error | Raised when |
| -- | -- |
| `SerialCommunicationError` | The serial port is unavailable, or the instrument doesn't complete its reply within 90 seconds. |
| `UnexpectedReturnValue` | The instrument's reply doesn't have the expected format, or contains an unknown error code. |
| `InvalidInstrumentStatusError` | The command isn't allowed in the current status, e.g. `Peel` while another command is running or after an error. |
| `InstrumentErrorDetected` | The instrument reports an error code, e.g. `Instrument error 04: Seal not removed.` If `treat_warnings_as_errors` is set, warnings also raise this error. |

## Getting started

### Cabling

Connect the computer running the connector to the instrument with a USB-to-serial (RS-232) cable.

### Prerequisites

* Python 3.10 or later
* [uv](https://docs.astral.sh/uv/) (recommended)

### Installation

Clone the repository and install the connector with its dependencies:

```sh
git clone https://github.com/plan5-labs/xpeel-sila2-connector.git
cd xpeel-sila2-connector
uv sync
```

The serial communication library `unitelabs-bus` is not on PyPI but on the UniteLabs package index, which `pyproject.toml` already configures for uv. To use pip in a virtual environment instead, install from the UniteLabs index, which also forwards the packages from PyPI:

```sh
python -m pip install . --index-url https://gitlab.com/api/v4/groups/1009252/-/packages/pypi/simple
```

The commands below assume uv. With pip, run them in the activated virtual environment without the `uv run` prefix.

### Configuration

Create a configuration file `config.json` in the current directory:

```sh
uv run config create --app unitelabs.xpeel:create_app
```

To see every option with its description, run `uv run config show --app unitelabs.xpeel:create_app`. These are the options for this connector:

| Option | Default | Description |
| -- | -- | -- |
| `serial_port` | `/dev/ttyUSB0` | The serial port the instrument is connected to, e.g. `COM3` on Windows. On Linux, prefer the stable name under `/dev/serial/by-id/`. |
| `simulation_mode` | `true` | Whether to start with a simulated instrument. **Set it to `false` to control the instrument.** |
| `treat_warnings_as_errors` | `false` | Whether commands fail when the instrument warns that the tape runs low, instead of returning the warning in `InstrumentWarningMessage`. |
| `sila_server.hostname` | `0.0.0.0` | The address the SiLA server listens on. Use `127.0.0.1` to accept local clients only. |
| `sila_server.port` | `50052` | The port the SiLA server listens on. |
| `sila_server.uuid` | random, written by `config create` | The server UUID, kept across restarts. |

The serial settings (9600 baud, 8 data bits, no parity, 1 stop bit) are fixed by the instrument.

### Usage

Start the connector:

```sh
uv run connector start --app unitelabs.xpeel:create_app
```

To use a configuration file at another path, add `--config-path <path>`. If the serial port can't be opened, the connector exits with an error.

Any SiLA 2 client can connect, e.g. the [SiLA Browser](https://gitlab.com/unitelabs/sila2/sila-browser) or the Python client that comes with the connector's dependencies:

```python
import asyncio

from sila.client import Client, ClientConfig


async def main():
    client = Client(ClientConfig(hostname="127.0.0.1", port=50052, tls=False))
    await client.open()

    controller = client.AutomatedPlateSealRemoverController
    print("Status:", await controller.Status.read())

    execution = await controller.Peel(BeginPeelLocation=4, AdhesionTime=1)
    async for _ in await execution.subscribe_status():
        pass  # wait until the command is done
    responses = await execution.get_responses()  # raises the command's error, if any
    print("Warning:", responses.InstrumentWarningMessage)

    await client.close()


asyncio.run(main())
```

### Simulation mode

By default, the connector starts in simulation mode with a simulated instrument, which completes every command instantly and without error. This lets you try the connector and test clients without hardware. To control the instrument, set `simulation_mode` to `false`, or call `SimulationController.StartRealMode` while the connector runs. If the serial port can't be opened, `StartRealMode` fails with `StartRealModeFailed` and the connector stays in simulation mode.

### Encryption

To encrypt the communication between the connector and its clients with TLS, generate a certificate and private key. This needs the optional `cryptography` package, which `--with` provides:

```sh
uv run --with cryptography certificate generate
```

This uses the UUID and hostname from `config.json` and offers to update `config.json` to enable TLS. With `--non-interactive` (`-y`), it updates `config.json` without asking, and with `--embed` (`-e`), it writes the certificate and key into `config.json` instead of separate files. If you configure TLS yourself, set these options under `sila_server`:

* `tls`: `true`
* `certificate_chain`: the path to the certificate, e.g. `cert.pem`
* `private_key`: the path to the private key, e.g. `key.pem`

Restart the connector after changing the configuration. Only `cert.pem` is needed by clients; never share `key.pem`.

### Docker

`docker-compose.yml` runs the connector with access to the serial ports and the host network. It reads the configuration from `./config.json`:

```sh
uv run config create --app unitelabs.xpeel:create_app
docker compose up --build
```

If the build fails with `No file descriptors available (os error 24)`, raise the open file limit for the build, e.g. `docker build --ulimit nofile=65536:65536 -t xpeel .`.

## Running in WSL2

When you run the connector in WSL, you must make the USB port that the instrument is connected to visible to WSL. See [USB passthrough](#usb-passthrough).

If clients on other computers on the same network need to reach the connector, you must also configure Windows (the host) to forward requests to WSL (the guest). See [Forwarding requests from Windows to WSL](#forwarding-requests-from-windows-to-wsl).

### USB passthrough

When the instrument is connected with a USB-to-serial (RS-232) cable, only Windows detects it. To make it available in WSL, pass the USB device from Windows to WSL with usbipd-win.

> **Note:** While the device is passed through, Windows no longer detects the instrument. To make Windows detect it again, [detach it from WSL](#detach-from-wsl).

#### Set up usbipd-win

Do this once.

1. (Windows) Install usbipd-win. Open PowerShell as administrator and run:

    ```ps1
    winget install --interactive --exact dorssel.usbipd-win
    ```

2. (Windows) Look up the device. Open **Device Manager** > **Ports (COM & LPT)** and find the port the instrument uses. Right-click it and select **Properties** > **Details**, then select **Device instance path**. Note the VID and PID in **Value**.

3. (Windows) Bind the device. Open a new PowerShell as administrator, so that usbipd-win is available, and list the devices. Find the BUSID of the device with the VID and PID from step 2:

    ```ps1
    usbipd list
    ```

    Then bind the device:

    ```ps1
    usbipd bind --busid <BUSID>
    ```

#### Attach to WSL

Do this every time you pass the device through.

1. (Windows) Find the BUSID of the device as in step 2 and 3 above with `usbipd list`, then attach the device to WSL:

    ```ps1
    usbipd attach --wsl --busid <BUSID>
    ```

2. (WSL) Find the name of the serial port, e.g. `ttyUSB0`:

    ```sh
    lsusb
    dmesg | grep -i tty
    ```

3. (WSL) Set `serial_port` in `config.json` to the full path of the serial port, e.g. `/dev/ttyUSB0`, and start the connector.

#### Detach from WSL

(Windows) In PowerShell, run:

```ps1
usbipd detach --busid <BUSID>
```

### Forwarding requests from Windows to WSL

Use one of these two methods.

#### Enable WSL mirrored mode

In mirrored mode, WSL shares the network and the IP address of Windows.

1. On the computer that runs the connector, open **WSL Settings**.
2. Select **Network**.
3. Set **Network mode** to **Mirrored** and turn on **Host address loopback**.
4. Restart WSL by running this in a Command Prompt:

    ```cmd
    wsl --shutdown
    ```

5. Keep `sila_server.hostname` at `0.0.0.0` in `config.json`.

#### Forward a port from Windows to WSL

This forwards the traffic for a port on Windows to WSL.

1. Open PowerShell as administrator.
2. Allow the port through the firewall, inbound and outbound:

    ```ps1
    New-NetFireWallRule -DisplayName 'WSL 2 Firewall Unlock' -Direction Outbound -RemoteAddress LocalSubnet -LocalPort <Port Number> -Action Allow -Protocol TCP
    New-NetFireWallRule -DisplayName 'WSL 2 Firewall Unlock' -Direction Inbound -RemoteAddress LocalSubnet -LocalPort <Port Number> -Action Allow -Protocol TCP
    ```

3. Forward the port to WSL:

    ```ps1
    netsh interface portproxy add v4tov4 listenport=<Port Number> listenaddress=* connectport=<Port Number> connectaddress=<WSL2 IP Address>
    ```

When you no longer need them, remove the firewall rules and the forwarding:

```ps1
Remove-NetFireWallRule -DisplayName 'WSL 2 Firewall Unlock'
netsh interface portproxy delete v4tov4 listenport=<Port Number> listenaddress=*
```

## Migrating from xpeel-sila2

The SiLA interface is unchanged, but the server is configured and started differently:

| xpeel-sila2 | This connector |
| -- | -- |
| `config.ini`: `COMPORT` `name` | `serial_port` |
| `config.ini`: `COMPORT` `baudrate`, `parity`, `bytesize`, `stopbits` | Fixed at 9600 baud, 8N1 |
| `config.ini`: `COMPORT` `timeout` | Fixed at 90 seconds for a command's complete reply |
| `config.ini`: `APPLICATION` `treat_warnings_as_errors` | `treat_warnings_as_errors` |
| `app.env`: `IP_ADDRESS`, `PORT` | `sila_server.hostname`, `sila_server.port` |
| `app.env`: `SERVER_UUID` | `sila_server.uuid` |
| `app.env`: `ENABLE_TLS`, `CERT_FILE`, `PRIVATE_KEY` | `sila_server.tls`, `sila_server.certificate_chain`, `sila_server.private_key` |
| `log_conf.yml` | `logging` in `config.json` (a Python `logging.config` dictionary) |
| `launch.sh` | `uv run connector start --app unitelabs.xpeel:create_app` |
| No simulation | `simulation_mode`, `true` by default |

Other changes:

* The server type is `Desealer` instead of `PeelerServer`, and the server name is `Azenta XPeel`. To keep the old values, set `sila_server.type` and `sila_server.name` in `config.json`.
* The status becomes Not Connected when the serial connection drops. Before, it stayed at its last value.
* If the instrument's reply contains an error code, `InstrumentErrorDetected` is raised even if the rest of the reply is unexpected, and its message includes the code, e.g. `Instrument error 04: Seal not removed.`
* The connector no longer includes a generated Python client. Use any SiLA 2 client, as shown in [Usage](#usage).

## Development

Set up the development environment and run the tests:

```sh
uv sync --all-extras
uv run pytest
```

Format and lint the code:

```sh
uv run ruff format src/ tests/
uv run ruff check src/ tests/
```

To restart the connector automatically whenever a source file changes, run it in dev mode:

```sh
uv run connector dev --app unitelabs.xpeel:create_app
```

The code is split into two layers:

* `src/unitelabs/xpeel/io/` talks to the instrument: the RS-232 command set (`protocol.py`, `commands.py`), the instrument's error codes, the status tracking, and the simulated instrument (`simulation.py`).
* `src/unitelabs/xpeel/features/` defines the SiLA features and delegates to `io/`.
