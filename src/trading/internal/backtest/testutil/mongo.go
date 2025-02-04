package testutil

import (
	"context"
	"fmt"
	"os"
	"testing"
	"time"

	"github.com/ory/dockertest/v3"
	"github.com/ory/dockertest/v3/docker"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

// StartMongoContainer starts a MongoDB container for testing
func StartMongoContainer(t *testing.T) (string, func()) {
	pool, err := dockertest.NewPool("")
	if err != nil {
		t.Fatalf("Could not connect to docker: %s", err)
	}

	// Pull MongoDB image and run container
	resource, err := pool.RunWithOptions(&dockertest.RunOptions{
		Repository: "mongo",
		Tag:        "4.4",
		Env: []string{
			"MONGO_INITDB_ROOT_USERNAME=root",
			"MONGO_INITDB_ROOT_PASSWORD=password",
		},
	}, func(config *docker.HostConfig) {
		config.AutoRemove = true
		config.RestartPolicy = docker.RestartPolicy{
			Name: "no",
		}
	})
	if err != nil {
		t.Fatalf("Could not start resource: %s", err)
	}

	// Set cleanup timeout
	if err := resource.Expire(120); err != nil {
		t.Fatalf("Could not set cleanup timeout: %s", err)
	}

	// Get host and port
	hostAndPort := resource.GetHostPort("27017/tcp")
	uri := fmt.Sprintf("mongodb://root:password@%s", hostAndPort)

	// Wait for MongoDB to be ready
	if err := pool.Retry(func() error {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()

		client, err := mongo.Connect(ctx, options.Client().ApplyURI(uri))
		if err != nil {
			return err
		}
		defer client.Disconnect(ctx)

		return client.Ping(ctx, nil)
	}); err != nil {
		t.Fatalf("Could not connect to docker: %s", err)
	}

	cleanup := func() {
		if err := pool.Purge(resource); err != nil {
			t.Errorf("Could not purge resource: %s", err)
		}
	}

	return uri, cleanup
}

// SkipIfNoDocker skips the test if Docker is not available
func SkipIfNoDocker(t *testing.T) {
	if os.Getenv("SKIP_DOCKER_TESTS") != "" {
		t.Skip("Skipping test that requires Docker")
	}

	pool, err := dockertest.NewPool("")
	if err != nil {
		t.Skip("Could not connect to Docker")
	}

	if err := pool.Client.Ping(); err != nil {
		t.Skip("Docker not available")
	}
}
