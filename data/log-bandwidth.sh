#!/usr/bin/env bash
export PATH="$HOME/homebox/env/bin:$PATH"
echo "$(date --rfc-3339=seconds): $(homeboxctl bandwidth) ($(homeboxctl wan-ip))" >> $HOME/homebox/bandwidth.log
