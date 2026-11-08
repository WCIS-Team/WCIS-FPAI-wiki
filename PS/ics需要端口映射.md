$linuxIP = "192.168.137.42"
$port    = 8091

# 1) netsh 端口代理（永久、重启不丢）
netsh interface portproxy add v4tov4 listenport=$port listenaddress=0.0.0.0 connectport=$port connectaddress=$linuxIP

# 2) 防火墙入站放行（专用/公用/域 全放）
New-NetFirewallRule -DisplayName "ICS Web Forward $port" -Direction Inbound -LocalPort $port -Protocol TCP -Action Allow -Profile Any

Write-Host "已映射 0.0.0.0:$port -> $linuxIP:$port"




ip addr flush dev eth0
ip addr add 192.168.137.228/24 dev eth0
ip link set eth0 up
ip route replace default via 192.168.137.1 dev eth0