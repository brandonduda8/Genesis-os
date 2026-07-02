from genesis.kernel.genesis_kernel import GenesisKernel
from origami.bootstrap import build_origami

print("🚀 Booting Genesis...")

kernel = GenesisKernel()
kernel.boot()

print("🦢 Building Origami...")

origami = build_origami(kernel)
origami.boot()

print("\n✅ Development environment ready!")
print("You now have:")
print("  • kernel")
print("  • origami")
print("\nTry:")
print("  print(origami.executor.providers.list())")
print("  print(origami.executor.providers.health())")
print("  print(origami.execute('Design a distributed AI platform'))")
