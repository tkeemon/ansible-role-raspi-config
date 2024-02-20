WIP Ansible Role: raspi-config
=========

*This role is still a work in progress. Use at your own risk*

An Ansible role that duplicates functionality of the raspi-config utility for the Raspberry Pi Operating System.

Requirements
------------

None

Role Variables
--------------

Every variable in defaults/main.yml should mirror the default state of a freshly installed Raspberry Pi OS. Editing the variables and running the role will update the OS state accordingly.

The tasks are organized to reflect the order of the options in the raspi-config UI. Each submenu cooresponds to a different file in the tasks directory. e.g. tasks/system.yml contains all of the tasks in system submenu of raspi-config.

Tags are used extensive throughout this role in order to make individual changes without running the full role. Tags generally follow the format:

```yaml
raspi_config:SUBMENU_NAME:TASK_NAME
```

e.g.:

```yaml
raspi_config:interface:ssh
```

If a set of tasks enable or disable a particular state, those states are taged with:

```yaml
raspi_config:SUBMENU_NAME:TASK_NAME:enable
# or
raspi_config:SUBMENU_NAME:TASK_NAME:disable
```

e.g.

```yaml
raspi_config:interface:ssh:enable
# or
raspi_config:interface:ssh:disable
```

Dependencies
------------

None

Example Playbook
----------------

```yaml
- name: "Configure Rasperry Pi via raspi_config"
  hosts: all
  become: True
  gather_facts: False
  vars:
    raspi_config_enable_ssh: True
  roles:
    - tkeemon.raspi_config
```

License
-------

MIT
