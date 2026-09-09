"""PowerShell-native scope and managed output adapters."""


def quote(value: str) -> str:
    """Quote a PowerShell literal without expression interpolation.

    :param value: Literal value.
    :returns: Single-quoted PowerShell literal.
    """
    return "'" + value.replace("'", "''") + "'"


def wrapper(text: str, token: str, script: bool, channels: dict[str, str]) -> str:
    """Select raw bridge or native script status reporting.

    :param text: Trusted invocation of a private script or bridge.
    :param token: Random command marker.
    :param script: Whether managed script streams need adaptation.
    :param channels: Business pipe endpoints.
    :returns: Native PowerShell wrapper.
    """
    if script:
        return script_wrapper(text, token, channels)
    return f"{text}\n[Console]::Out.WriteLine('{token}:' + $LASTEXITCODE)\n"


def script_wrapper(invocation_text: str, token: str, channels: dict[str, str]) -> str:
    """Render PowerShell script streams without Out-File's multiple pipe opens.

    :param invocation_text: Dot-source expression for the native script.
    :param token: Private completion token.
    :param channels: Private business stream endpoints.
    :returns: PowerShell script with independent managed output and error writers.
    """
    output = quote(channels["stdout"])
    error = quote(channels["stderr"])
    source = quote(channels["stdin"])
    return f"""$sn_out = [IO.File]::OpenWrite({output})
$sn_err = [IO.File]::OpenWrite({error})
$sn_in = [IO.File]::OpenRead({source})
$sn_encoding = [Text.UTF8Encoding]::new($false)
$sn_writer = [IO.StreamWriter]::new($sn_out, $sn_encoding)
$sn_error_writer = [IO.StreamWriter]::new($sn_err, $sn_encoding)
$sn_reader = [IO.StreamReader]::new($sn_in, $sn_encoding)
$sn_writer.AutoFlush = $true
$sn_error_writer.AutoFlush = $true
$sn_saved_out = [Console]::Out
$sn_saved_err = [Console]::Error
$sn_saved_in = [Console]::In
$sn_saved_handle = [ShellNext.StandardInput]::GetStdHandle(-10)
$sn_input_handle = $sn_in.SafeFileHandle.DangerousGetHandle()
if (-not [ShellNext.StandardInput]::SetHandleInformation($sn_input_handle, 1, 1)) {{
    throw 'Unable to configure native business input inheritance'
}}
if (-not [ShellNext.StandardInput]::SetStdHandle(-10, $sn_input_handle)) {{
    throw 'Unable to configure native business input'
}}
[Console]::SetOut($sn_writer)
[Console]::SetError($sn_error_writer)
[Console]::SetIn($sn_reader)
$sn_terminating = $false
$sn_success = $true
try {{
    {invocation_text} *>&1 | ForEach-Object {{
        if ($_ -is [Management.Automation.ErrorRecord]) {{
            $sn_error_writer.WriteLine($_.ToString())
            $sn_success = $false
        }} else {{ $sn_writer.WriteLine($_.ToString()) }}
    }}
    $sn_success = $sn_success -and $?
}} catch {{
    $sn_terminating = $true
    $sn_success = $false
    $sn_error_writer.WriteLine($_.ToString())
}} finally {{
    [Console]::SetOut($sn_saved_out)
    [Console]::SetError($sn_saved_err)
    [Console]::SetIn($sn_saved_in)
    $null = [ShellNext.StandardInput]::SetStdHandle(-10, $sn_saved_handle)
    $sn_writer.Dispose()
    $sn_error_writer.Dispose()
    $sn_reader.Dispose()
}}
$sn_result = @{{ success=$sn_success; native=$LASTEXITCODE; terminating=$sn_terminating }}
[Console]::Out.WriteLine('{token}:' + (ConvertTo-Json -Compress $sn_result))
"""
