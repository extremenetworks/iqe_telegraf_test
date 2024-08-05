Run tests in Windows 11 env.  

Requirements:
pytest
aiohttp
pytest-aiohttp
paramiko

During tests, telegraf server saves received cpu stats in telegraf_stats_*.json,
and AP CPU reading is saved in <apIp>_ap_*_show.txt. Server IP and AP IP must in the same subnet.

To run test, in test directory:
#pytest -v .

To run test with console printout:
#pytest -v -s .

Recommand REST Client in vscode:

Id: humao.rest-client

Description: REST Client for Visual Studio Code

Version: 0.25.1
Publisher: Huachao Mao

VS Marketplace Link: https://marketplace.visualstudio.com/items?itemName=humao.rest-client.

See examples in client.http to POST and GET
  
