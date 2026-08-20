#!/usr/bin/env bash
export PATH="$HOME/homebox/env/bin:$PATH"
time=$(date --rfc-3339=seconds)
wan_ip=$(homeboxctl wan-ip)
bandwidth=$(homeboxctl bandwidth)
echo "$time: $bandwidth ($wan_ip)" >> $HOME/homebox/bandwidth.log
