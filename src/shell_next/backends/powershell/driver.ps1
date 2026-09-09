# Private persistent host. The sn_ namespace is reserved for the session protocol.
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace ShellNext {
    public static class StandardInput {
        [DllImport("kernel32.dll", SetLastError = true)]
        public static extern IntPtr GetStdHandle(int kind);
        [DllImport("kernel32.dll", SetLastError = true)]
        public static extern bool SetStdHandle(int kind, IntPtr handle);
        [DllImport("kernel32.dll", SetLastError = true)]
        public static extern bool SetHandleInformation(IntPtr handle, uint mask, uint flags);
    }
}
'@
$ErrorActionPreference = 'Continue'
$sn_control = [Console]::In
[Console]::Out.WriteLine('shell-next-session-ready')
while ($null -ne ($sn_path = $sn_control.ReadLine())) {
    . $sn_path
}
