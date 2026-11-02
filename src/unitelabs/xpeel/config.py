import dataclasses
from importlib.metadata import version

from unitelabs.cdk import ConnectorBaseConfig, SiLAServerConfig

__version__ = version("unitelabs-xpeel")


@dataclasses.dataclass
class XPeelConfig(ConnectorBaseConfig):
    """Configuration for the Azenta XPeel."""

    sila_server: SiLAServerConfig = dataclasses.field(
        default_factory=lambda: SiLAServerConfig(
            port=50052,
            name="Azenta XPeel",
            type="Desealer",
            description=(
                """
                A connector for the Automated Plate Seal Remover (formerly known as XPeel) by Azenta Life Sciences,
                built with the UniteLabs CDK.
                """
            ),
            version=str(__version__),
            vendor_url="https://github.com/plan5-labs/xpeel-sila2-connector",
        )
    )

    serial_port: str = "/dev/ttyUSB0"
    """
    The serial port the instrument is connected to, e.g. `/dev/ttyUSB0` on Linux or `COM3` on Windows.
    On Linux, prefer the stable name under `/dev/serial/by-id/`.
    """

    simulation_mode: bool = True
    """Whether to start with a simulated instrument instead of the instrument on `serial_port`."""

    treat_warnings_as_errors: bool = False
    """
    Whether commands fail when the instrument warns that the tape runs low, instead of returning the warning in
    their `InstrumentWarningMessage` response.
    """
