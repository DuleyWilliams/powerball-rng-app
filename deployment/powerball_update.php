<?php

declare(strict_types=1);

/**
 * IONOS HTTP GET cron trigger for the Powerball daily updater.
 *
 * Deploy this file to: /jobs/powerball_update.php
 * Public URL:          https://duleywilliams.com/jobs/powerball_update.php
 *
 * It does exactly one thing: after verifying a secret token, it runs the
 * already-existing, already-protected shell script
 *
 *   /kunden/homepages/8/d230686207/htdocs/powerball-cron/powerball-rng-app/lotto-app/run_cron_update.sh
 *
 * via its absolute path and reports the result as JSON. It never touches
 * the Python updater or the Streamlit app directly, and it does not
 * change or bypass the existing "Require all denied" protection on
 * /powerball-cron — that directory stays unreachable over HTTP; this
 * script only invokes the shell script as a local OS process on the same
 * server, which is unrelated to Apache's HTTP-level access control.
 *
 * Auth: requires ?token=<secret>, compared with hash_equals() against the
 * value returned by powerball_update.secret.php, which sits next to this
 * file on the server but is NOT committed to git — see
 * powerball_update.secret.php.example and the deployment instructions.
 */

// ---------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------

const UPDATER_SCRIPT = '/kunden/homepages/8/d230686207/htdocs/powerball-cron/powerball-rng-app/lotto-app/run_cron_update.sh';
const EXEC_TIMEOUT_SECONDS = 55;
const SECRET_FILE = __DIR__ . '/powerball_update.secret.php';

// Defense in depth for the PHP layer itself. This does NOT reliably
// interrupt the blocking child process below — PHP does not count time
// spent in a blocking system call against max_execution_time. The real
// timeout enforcement is the proc_open() polling loop further down. See
// "Security limitations" in the deployment notes.
set_time_limit(EXEC_TIMEOUT_SECONDS);

ini_set('display_errors', '0');
error_reporting(E_ALL);

header('Content-Type: application/json; charset=utf-8');

// Catch-all so no circumstance (typo, disabled function, malformed
// secret file, etc.) can leak a raw PHP error page or stack trace.
set_exception_handler(static function (Throwable $e): void {
    error_log('powerball_update.php: uncaught ' . get_class($e) . ': ' . $e->getMessage());
    if (!headers_sent()) {
        header('Content-Type: application/json; charset=utf-8');
    }
    http_response_code(500);
    echo json_encode(['success' => false, 'message' => 'Internal error.']);
    exit;
});

// ---------------------------------------------------------------------
// Response helpers — every exit point goes through these so the shape
// and information exposed is consistent and deliberate.
// ---------------------------------------------------------------------

function respond(int $httpStatus, array $payload): void
{
    http_response_code($httpStatus);
    echo json_encode($payload, JSON_UNESCAPED_SLASHES);
    exit;
}

/** Identical response whether the token is missing, malformed, or wrong
 * — never reveal which, to avoid giving an attacker a validity signal. */
function denyAsForbidden(): void
{
    respond(403, [
        'success' => false,
        'message' => 'Forbidden.',
    ]);
}

/** For our own misconfiguration — logged server-side only, never in the
 * HTTP response. */
function failClosed(string $logDetail): void
{
    error_log('powerball_update.php: ' . $logDetail);
    respond(500, [
        'success' => false,
        'message' => 'Server misconfigured.',
    ]);
}

// ---------------------------------------------------------------------
// Authentication
// ---------------------------------------------------------------------

function loadExpectedToken(): ?string
{
    $envToken = getenv('POWERBALL_CRON_TOKEN');
    if (is_string($envToken) && $envToken !== '') {
        return $envToken;
    }

    if (is_file(SECRET_FILE) && is_readable(SECRET_FILE)) {
        $token = require SECRET_FILE;
        if (is_string($token) && $token !== '') {
            return $token;
        }
    }

    return null;
}

$expectedToken = loadExpectedToken();
if ($expectedToken === null) {
    failClosed(
        'no secret token configured (missing POWERBALL_CRON_TOKEN env var '
        . 'and unreadable/missing ' . SECRET_FILE . ')'
    );
}

$providedToken = $_GET['token'] ?? '';
if (!is_string($providedToken) || $providedToken === '' || !hash_equals($expectedToken, $providedToken)) {
    denyAsForbidden();
}

// ---------------------------------------------------------------------
// Preflight checks
// ---------------------------------------------------------------------

if (!function_exists('proc_open')) {
    // proc_open() is what lets us actually enforce EXEC_TIMEOUT_SECONDS by
    // terminating a runaway process — plain exec()/shell_exec() can't be
    // interrupted this way. Hosts that disable exec()/shell_exec() via
    // disable_functions almost always disable proc_open() too, so this
    // check serves the same "is command execution available" purpose.
    failClosed('proc_open() is disabled (disable_functions) — command execution unavailable.');
}

if (!is_file(UPDATER_SCRIPT) || !is_executable(UPDATER_SCRIPT)) {
    failClosed('updater script missing or not executable at the configured path.');
}

// ---------------------------------------------------------------------
// Run the updater with an enforced timeout
// ---------------------------------------------------------------------

/**
 * Runs $scriptPath with no shell interpretation (array-form proc_open,
 * PHP 7.4+), polling until it exits or $timeoutSeconds elapses, in which
 * case it is terminated (SIGTERM, then SIGKILL if still alive shortly
 * after). Returns exit code, output, and whether it timed out.
 */
function runUpdater(string $scriptPath, int $timeoutSeconds): array
{
    $descriptors = [
        0 => ['pipe', 'r'],
        1 => ['pipe', 'w'],
        2 => ['pipe', 'w'],
    ];

    $process = proc_open([$scriptPath], $descriptors, $pipes);

    if (!is_resource($process)) {
        return ['started' => false, 'exit_code' => null, 'timed_out' => false, 'stdout' => '', 'stderr' => ''];
    }

    fclose($pipes[0]);
    stream_set_blocking($pipes[1], false);
    stream_set_blocking($pipes[2], false);

    $stdout = '';
    $stderr = '';
    $start = microtime(true);
    $timedOut = false;

    while (true) {
        $stdout .= stream_get_contents($pipes[1]);
        $stderr .= stream_get_contents($pipes[2]);

        $status = proc_get_status($process);

        if (!$status['running']) {
            break;
        }

        if ((microtime(true) - $start) >= $timeoutSeconds) {
            $timedOut = true;
            proc_terminate($process, 15); // SIGTERM
            usleep(300000);
            $status = proc_get_status($process);
            if ($status['running']) {
                proc_terminate($process, 9); // SIGKILL
            }
            break;
        }

        usleep(100000);
    }

    $stdout .= stream_get_contents($pipes[1]);
    $stderr .= stream_get_contents($pipes[2]);

    fclose($pipes[1]);
    fclose($pipes[2]);

    $exitCode = proc_close($process);

    return [
        'started' => true,
        'exit_code' => $timedOut ? null : $exitCode,
        'timed_out' => $timedOut,
        'stdout' => $stdout,
        'stderr' => $stderr,
    ];
}

$requestStart = microtime(true);
$result = runUpdater(UPDATER_SCRIPT, EXEC_TIMEOUT_SECONDS);
$elapsedSeconds = round(microtime(true) - $requestStart, 3);

if (!$result['started']) {
    failClosed('proc_open() failed to start the updater process.');
}

// Server-side only — never sent to the HTTP caller. run_cron_update.sh
// normally redirects the Python updater's own output into
// lotto-app/logs/cron_update.log, so stdout/stderr here should usually be
// empty; anything present is worth a look via SSH/error_log, not exposed
// over HTTP.
if ($result['stdout'] !== '' || $result['stderr'] !== '') {
    error_log(sprintf(
        'powerball_update.php: updater produced output — stdout=%s stderr=%s',
        trim($result['stdout']),
        trim($result['stderr'])
    ));
}

// ---------------------------------------------------------------------
// Interpret the result
// ---------------------------------------------------------------------

if ($result['timed_out']) {
    respond(200, [
        'success' => false,
        'exit_code' => null,
        'message' => 'Updater timed out after ' . EXEC_TIMEOUT_SECONDS . ' seconds and was terminated.',
        'elapsed_seconds' => $elapsedSeconds,
        'timestamp' => date(DATE_ATOM),
    ]);
}

$exitCode = $result['exit_code'];

switch ($exitCode) {
    case 0:
        $success = true;
        $message = 'Updater completed successfully.';
        break;
    case 1:
        $success = false;
        $message = 'Updater reported a failure. Check lotto-app/logs/cron_update.log on the server for details.';
        break;
    case 2:
        $success = false;
        $message = 'Updater already running (lock held by another run).';
        break;
    default:
        $success = false;
        $message = 'Updater exited with an unexpected status.';
        break;
}

respond(200, [
    'success' => $success,
    'exit_code' => $exitCode,
    'message' => $message,
    'elapsed_seconds' => $elapsedSeconds,
    'timestamp' => date(DATE_ATOM),
]);
