package config

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
)

type Secrets struct {
	PumpFunKey string `json:"pump_fun_key"`
}

var encryptionKey = []byte("tradingbot-secure-32byte-key-here!!")

func encrypt(text string) (string, error) {
	block, err := aes.NewCipher(encryptionKey)
	if err != nil {
		return "", err
	}
	plaintext := []byte(text)
	ciphertext := make([]byte, aes.BlockSize+len(plaintext))
	iv := ciphertext[:aes.BlockSize]
	if _, err := io.ReadFull(rand.Reader, iv); err != nil {
		return "", err
	}
	stream := cipher.NewCFBEncrypter(block, iv)
	stream.XORKeyStream(ciphertext[aes.BlockSize:], plaintext)
	return base64.URLEncoding.EncodeToString(ciphertext), nil
}

func decrypt(cryptoText string) (string, error) {
	block, err := aes.NewCipher(encryptionKey)
	if err != nil {
		return "", err
	}
	ciphertext, err := base64.URLEncoding.DecodeString(cryptoText)
	if err != nil {
		return "", err
	}
	if len(ciphertext) < aes.BlockSize {
		return "", fmt.Errorf("ciphertext too short")
	}
	iv := ciphertext[:aes.BlockSize]
	ciphertext = ciphertext[aes.BlockSize:]
	stream := cipher.NewCFBDecrypter(block, iv)
	stream.XORKeyStream(ciphertext, ciphertext)
	return string(ciphertext), nil
}

func SaveSecrets(secrets *Secrets) error {
	keyPath := filepath.Join(os.Getenv("HOME"), ".config", "tradingbot", "secrets.json")
	encryptedKey, err := encrypt(secrets.PumpFunKey)
	if err != nil {
		return fmt.Errorf("failed to encrypt key: %w", err)
	}
	secrets.PumpFunKey = encryptedKey
	data, err := json.MarshalIndent(secrets, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal secrets: %w", err)
	}
	return os.WriteFile(keyPath, data, 0600)
}

func LoadSecrets() (*Secrets, error) {
	keyPath := filepath.Join(os.Getenv("HOME"), ".config", "tradingbot", "secrets.json")
	data, err := os.ReadFile(keyPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read secrets file: %w", err)
	}
	var secrets Secrets
	if err := json.Unmarshal(data, &secrets); err != nil {
		return nil, fmt.Errorf("failed to unmarshal secrets: %w", err)
	}
	decryptedKey, err := decrypt(secrets.PumpFunKey)
	if err != nil {
		return nil, fmt.Errorf("failed to decrypt key: %w", err)
	}
	secrets.PumpFunKey = decryptedKey
	return &secrets, nil
}
