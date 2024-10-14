# aind-behavior-experiment-laucher

Source for for a minimal framework that can be used to build experimental interfaces

---

## Introduction


The launcher module of this library provides a frontend interface to launch, monitor and manage behavior tasks using this library. It is also designed to interface with the AIND Services.

AIND Services Module
####################

While we will try to keep this library up to date, it is recommended to check the original repositories for the most recent updates.

A list of services relevant for this library include:

- [aind-data-schema](https://github.com/AllenNeuralDynamics/aind-data-schema)
- [aind-data-schema-models](https://github.com/AllenNeuralDynamics/aind-data-schema-models)
- [aind-watchdog-service](https://github.com/AllenNeuralDynamics/aind-watchdog-service)
- [aind-slims-api](https://github.com/AllenNeuralDynamics/aind-slims-api)
- [aind-data-mapper](https://github.com/AllenNeuralDynamics/aind-metadata-mapper)

We will generally try to wrap the services provided by these repositories into a more user-friendly and opinionated interface that can be used by the Aind Behavior Services library and other repositories.

We will also try to scope all dependencies of the related to AIND Services to its own optional dependency list in the `./pyproject.toml` file of this repository. Therefore, in order to use this module, you will need to install these optional dependencies by running:

```pip install .[aind-services]```

Feedback and contributions are welcome!

## General instructions

This repository follows the project structure laid out in the [Aind.Behavior.Services repository](https://github.com/AllenNeuralDynamics/Aind.Behavior.Services).


### Getting started

To get started, install the package by running:

```pip install .```

The entry point for the launcher is the `aind_behavior_experiment_launcher.launcher.Launcher` class. This class provides a framework to interface with the AIND Services and launch behavior tasks. While the class is designed to run as is, it is also designed to be extended and customized by overriding the methods provided in the class.

The remaining modules provide useful interfaces and wrappers that can be called by the `Launcher` class. Similarly to the `Launcher` class, these modules are designed to be extended and customized by inheriting from the base classes provided in the modules and overriding the respective interface methods.
