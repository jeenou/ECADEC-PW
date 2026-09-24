# Sets the shared RabbitMQ config and starts the message forwarder.
# Keep this exchange name in sync with the value used when starting ecadec_pw.simces_component.

$env:RABBITMQ_EXCHANGE = "procem.ecadec_pw_exchange"
$env:FORWARD_URL = "http://localhost:8000/messages"
$env:FORWARD_TOPIC = "#"

Set-Location $PSScriptRoot
.\.venv\Scripts\python.exe -m ecadec_pw.forwarder
