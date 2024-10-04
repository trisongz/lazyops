import os
import typing as t
from pydantic.networks import AnyHttpUrl
from lzl.logging import get_logger, change_logger_level, null_logger
logger_level: str = os.getenv('LOGGER_LEVEL', 'INFO').upper()
logger = get_logger(logger_level)

logger.set_module_name('lzl.api.aiorqlite', 'aiorqlite', is_relative = True)


def _parse_host(host: str, /, *, default_port: int = 4001) -> t.Tuple[str, int]:
    """Parses a host:port pair into an ip address and port.

    Args:
        host (str): A host:port pair, or just a host
        default_port (int): the port to assume if not specified; for configuration,
            this is 4001, for loading from the Location header, this depends on the
            protocol

    Returns:
        A tuple of (ip, port)
    """
    if not host:
        raise ValueError("host must not be empty")

    num_colons = host.count(":")
    if num_colons > 1:
        # ipv6; must be of the form [host]:port if port is specified
        if host[0] != "[":
            return host, 4001

        close_square_bracket_idx = host.find("]")
        return host[1:close_square_bracket_idx], int(
            host[close_square_bracket_idx + 1 :]
        )

    if num_colons == 0:
        return host, default_port

    hostname, port_str = host.split(":")
    return hostname, int(port_str)


def parse_host(
    host: t.Union[str, AnyHttpUrl],
    default_port: int = 4001,
) -> AnyHttpUrl:
    """
    Parses a host into an AnyHttpUrl
    """
    if isinstance(host, str):
        if '://' not in host: 
            host = f'http://{host}' if host.endswith(':4001') else f'https://{host}'
        host = host.replace('rqlites:', 'https:').replace('rqlite:', 'http:')
        host = AnyHttpUrl(host)
    # if not host.port: host.port = default_port
    return host
