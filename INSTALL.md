
## install Ansible 
> install ansbile then below command to install the required collection
```
ansible-galaxy collection install kubernetes.core
```
then
```
ansible-playbook -i inventory.yml playbook.yml --ask-vault-pass
```
## Exposed Services

| Service   | Port  |
| --------  | ----- |
| Immich    | 32283-k3s / 2283-docker |
| Navidrome | 4533  |
| Docmost   | 3000  |
| Jellyfin  | 8096  |
| ArgoCD UI	| 30100 |	