from __future__ import annotations

from typing import TYPE_CHECKING

from pdm import termui
from pdm.compat import Distribution
from pdm.exceptions import UninstallError
from pdm.installers.installers import install_wheel, install_wheel_with_cache
from pdm.installers.uninstallers import BaseRemovePaths, StashedRemovePaths

if TYPE_CHECKING:
    from pdm.environments import BaseEnvironment
    from pdm.models.candidates import Candidate


class InstallManager:
    """The manager that performs the installation and uninstallation actions."""

    # The packages below are needed to load paths and thus should not be cached.
    NO_CACHE_PACKAGES = ("editables",)

    def __init__(self, environment: BaseEnvironment, *, use_install_cache: bool = False) -> None:
        self.environment = environment
        self.use_install_cache = use_install_cache

    def install(self, candidate: Candidate) -> Distribution:
        """Install a candidate into the environment, return the distribution"""
        if self.use_install_cache and candidate.req.is_named and candidate.name not in self.NO_CACHE_PACKAGES:
            # Only cache wheels from PyPI
            installer = install_wheel_with_cache
        else:
            installer = install_wheel
        prepared = candidate.prepare(self.environment)
        dist_info = installer(str(prepared.build()), self.environment, prepared.direct_url())
        return Distribution.at(dist_info)

    def get_paths_to_remove(self, dist: Distribution) -> BaseRemovePaths:
        """Get the path collection to be removed from the disk"""
        return StashedRemovePaths.from_dist(dist, environment=self.environment)

    def uninstall(self, dist: Distribution) -> None:
        """Perform the uninstallation for a given distribution"""
        remove_path = self.get_paths_to_remove(dist)
        dist_name = dist.metadata["Name"]
        termui.logger.info("Removing distribution %s", dist_name)
        try:
            remove_path.remove()
            remove_path.commit()
        except OSError as e:
            termui.logger.info("Error occurred during uninstallation, roll back the changes now.")
            remove_path.rollback()
            raise UninstallError(e) from e

    def overwrite(self, dist: Distribution, candidate: Candidate) -> None:
        """An in-place update to overwrite the distribution with a new candidate"""
        paths_to_remove = self.get_paths_to_remove(dist)
        termui.logger.info("Overwriting distribution %s", dist.metadata["Name"])
        installed = self.install(candidate)
        installed_paths = self.get_paths_to_remove(installed)
        # Remove the paths that are in the new distribution
        paths_to_remove.difference_update(installed_paths)
        try:
            paths_to_remove.remove()
            paths_to_remove.commit()
        except OSError as e:
            termui.logger.info("Error occurred during overwriting, roll back the changes now.")
            raise UninstallError(e) from e
