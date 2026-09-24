# Sets the shared RabbitMQ config and starts the SimCES coordination component.
# Keep this exchange name in sync with the value used when starting ecadec_pw.forwarder.

$env:RABBITMQ_EXCHANGE = "procem.ecadec_pw_exchange"

Set-Location $PSScriptRoot
.\.venv\Scripts\python.exe -m ecadec_pw.simces_component
