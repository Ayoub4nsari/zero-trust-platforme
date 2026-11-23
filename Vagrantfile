Vagrant.configure("2") do |config|
  config.vm.box = "bento/ubuntu-24.04"
  config.vm.hostname = "zerotrust"

  # Démarrage lent possible (VirtualBox + Hyper-V/WSL2) : on laisse 15 min
  config.vm.boot_timeout = 1800

  # Seul HTTPS (Caddy) est exposé ; Keycloak et Notification n'ont aucun port publié
  config.vm.network "forwarded_port", guest: 8443, host: 8443, host_ip: "127.0.0.1"

  # Projet monté en lecture seule : la VM ne peut rien modifier côté Windows
  config.vm.synced_folder ".", "/vagrant", mount_options: ["ro"]

  config.vm.provider "virtualbox" do |vb|
    vb.name = "zerotrust"
    vb.memory = 4096
    vb.cpus = 2
    vb.gui = false   # n'affiche paas l'écran de la VM pour diagnostiquer
  end

  # 1re fois seulement : Docker, pare-feu
  config.vm.provision "setup", type: "shell", path: "scripts/provision-vm.sh", privileged: true
  # À chaque "vagrant up" / "vagrant provision" : copie du code, secrets, certs, docker compose up
  config.vm.provision "deploy", type: "shell", path: "scripts/deploy-vm.sh", privileged: false, run: "always"
end