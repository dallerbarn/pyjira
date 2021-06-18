# PyJira

PyJira is a command line interface for Jira 

## Installation

Clone the git repo to your local computer
```bash
git clone ...
```

Go to the project root folder and use the package manager [pip](https://pip.pypa.io/en/stable/) to install pyJira.

```bash
cd pyjira
pip install -g .
```

## Configuration

The configure command will start a wizard for configuring the jira cli.  
 
```bash
jira configure
```

As a default the config file will be written in the user home folder *~/pyjira.yaml*

Optionally this file path can be changed by setting the environment variable *PYJIRA_CONFIG*

```bash
set PYJIRA_CONFIG=<file-path> 
```

## Usage
 
```bash
Usage: jira [OPTIONS] COMMAND [ARGS]...

Options:
  --version   Show the version and exit.
  -h, --help  Show this message and exit.

Commands:
  configure  Configure the cli
  dashboard  Start an interactive dashboard
  ls         List all issues assigned to the current user
  show       Show detailed information about a specific issue
```

## Contributing
Pull requests are welcome.

