<?php

namespace App;

use Telegram\Bot\Api;
use Telegram\Bot\Objects\Update;

class BotHandler
{
    protected Api $telegram;
    protected string $adminUsername;
    protected string $dataFile;

    public function __construct(string $token, string $adminUsername)
    {
        $this->telegram = new Api($token);
        $this->adminUsername = $adminUsername;
        $this->dataFile = __DIR__ . '/../data/users.json';
    }

    /**
     * Handles the incoming update from Telegram.
     */
    public function handle(): void
    {
        // Get the webhook update
        $update = $this->telegram->getWebhookUpdate();
        $message = $update->getMessage();
        $chatId = $message->getChat()->getId();

        // We only care about group/channel updates
        if ($chatId > 0) {
            return;
        }

        // Handle new chat members
        if ($message->getNewChatMembers()) {
            foreach ($message->getNewChatMembers() as $user) {
                $this->recordUserJoin($user->getId());
            }
        }

        // Handle a user leaving
        if ($message->getLeftChatMember()) {
            $user = $message->getLeftChatMember();
            $this->handleUserLeave($user->getId(), $chatId);
        }
    }

    /**
     * Records the join time of a user.
     */
    private function recordUserJoin(int $userId): void
    {
        $users = $this->getUsers();
        $users[$userId] = time();
        file_put_contents($this->dataFile, json_encode($users), LOCK_EX);
    }

    /**
     * Checks if a user should be banned.
     */
    private function handleUserLeave(int $userId, int $chatId): void
    {
        $users = $this->getUsers();
        $this->cleanOldUsers($users); // Housekeeping

        if (!isset($users[$userId])) {
            return; // User was not in our records, do nothing.
        }

        $joinTime = $users[$userId];
        $timeDiff = time() - $joinTime;

        // If the user left within 5 minutes (300 seconds)
        if ($timeDiff < 300) {
            $this->banUser($userId, $chatId);
        }

        // Remove user from records regardless of ban status
        unset($users[$userId]);
        file_put_contents($this->dataFile, json_encode($users), LOCK_EX);
    }

    /**
     * Bans the user and sends a message.
     */
    private function banUser(int $userId, int $chatId): void
    {
        try {
            // Ban the user from the chat
            $this->telegram->banChatMember([
                'chat_id' => $chatId,
                'user_id' => $userId,
                'revoke_messages' => true, // Optional: removes all messages from the user
            ]);

            // Send a message to the banned user (if possible)
            $this->telegram->sendMessage([
                'chat_id' => $userId,
                'text' => "You have been automatically banned for leaving the group too quickly.\n\nTo appeal, please contact the admin: @{$this->adminUsername}",
                'parse_mode' => 'Markdown',
            ]);
        } catch (\Exception $e) {
            // Log error if needed, e.g., error_log($e->getMessage());
        }
    }

    /**
     * Loads user data from the JSON file.
     * @return array
     */
    private function getUsers(): array
    {
        if (!file_exists($this->dataFile)) {
            return [];
        }
        $json = file_get_contents($this->dataFile);
        return json_decode($json, true) ?? [];
    }

    /**
     * Cleans up old user records to prevent the file from growing indefinitely.
     */
    private function cleanOldUsers(array &$users): void
    {
        $now = time();
        foreach ($users as $userId => $joinTime) {
            // Remove users who joined more than an hour ago
            if ($now - $joinTime > 3600) {
                unset($users[$userId]);
            }
        }
    }
}
