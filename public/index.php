<?php

require_once __DIR__ . '/../vendor/autoload.php';

use App\BotHandler;

// Security check: Verify the secret token from Telegram
 $secretToken = getenv('TELEGRAM_SECRET_TOKEN');
if (!isset($_SERVER['HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN']) || $_SERVER['HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN'] !== $secretToken) {
    http_response_code(403);
    die('Forbidden');
}

// Get the Telegram Bot Token and Admin Username from environment variables
 $botToken = getenv('TELEGRAM_BOT_TOKEN');
 $adminUsername = getenv('ADMIN_USERNAME');

if (!$botToken || !$adminUsername) {
    http_response_code(500);
    die('Server configuration error.');
}

// Create and handle the bot request
 $botHandler = new BotHandler($botToken, $adminUsername);
 $botHandler->handle();

// Respond to Telegram with a 200 OK to prevent retries
http_response_code(200);
