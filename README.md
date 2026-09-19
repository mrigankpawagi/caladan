# Caladan

Caladan is a system that enables servers in datacenters to
simultaneously provide low tail latency and high CPU efficiency, by
rapidly reallocating cores across applications.

### Contact

For any questions about Caladan, please email <caladan@csail.mit.edu>.

## How to Run Caladan

1) Clone the Caladan repository.

2) Install dependencies.

```
sudo apt install \
  make gcc cmake pkg-config \
  libnl-3-dev libnl-route-3-dev libnuma-dev uuid-dev libssl-dev \
  libaio-dev libcunit1-dev libclang-dev libncurses-dev meson \
  python3-pyelftools libarchive-dev
```

3) Set up submodules (e.g., DPDK, SPDK, and rdma-core).

```
make submodules
```

4) Build the scheduler (IOKernel), the Caladan runtime, and Ksched, and perform machine setup.
Before building, optionally set parameters in build/config (e.g., `CONFIG_SPDK=y` to enable
storage support). To enable debugging, set `CONFIG_DEBUG=y`.
```
make clean && make
pushd ksched
make clean && make
popd
sudo ./scripts/setup_machine.sh
```

5) Install Rust and build the loadgen client-server application.

```
curl https://sh.rustup.rs -sSf | sh -s -- -y --default-toolchain=nightly
```
```
cd apps/loadgen
cargo build --release
```

6) Run the loadgen application with a client and server. The client
sends requests to the server, which performs a specified amount of
fake work (e.g., computing square roots for 10us), before responding.

On the server:
```
sudo ./iokerneld
./apps/loadgen/target/release/loadgen 192.168.1.3:5000 --config server.config --mode spawner-server
```

On the client:
```
sudo ./iokerneld
./apps/loadgen/target/release/loadgen 192.168.1.3:5000 --config client.config --mode runtime-client
```

## Supported Platforms

This code was originally developed and tested on Ubuntu 18.04 with kernel
5.2.0 and Ubuntu 20.04 with kernel 5.4.0. Most recently it has been confirmed
to run on Ubuntu 22.04 (kernel 5.15) and Ubuntu 24.04 (kernel 6.8).

### NICs

Caladan performs best using its own mlx5 driver which is compatible with
ConnectX-4 and newer NVIDIA/Mellanox NICs. However, it can also use DPDK for
networking in a lower performance configuration. Recently tested and confirmed
working DPDK pmds include: ixgbe, i40e, ice, bnxt, mana, failsafe, mlx5, and
tap; mlx4 is not supported. Please contact us if there is another PMD which you
need help enabling.

To enable Jumbo Frames for higher throughput, first enable them in Linux on the
relevant interface like so:
```
ip link set eth0 mtu 9000
```
Then use the (`host_mtu`) option in the config file of each runtime to set the
MTU to the value you'd like, up to the size of the MTU set for the interface.

#### Directpath
Directpath allows runtime cores to directly send packets to/receive packets
from the NIC, enabling higher throughput than when the IOKernel handles all
packets. Directpath is currently only supported with Mellanox ConnectX-4 and
newer NICs. Standard and VFIO directpath differ in who owns the NIC:

| | Standard directpath | VFIO directpath |
|---|---|---|
| NIC driver | Kernel `mlx5_core`; Linux interface stays up | `vfio-pci`; no Linux interface |
| Queue and steering setup | Each runtime sets up its own | IOKernel |
| Runtime config | `enable_directpath 1` | _None_ |
| Runtimes need root | Yes | No |
| IOKernel arguments | `nicpci <pci address>` | `vfio nicpci <pci address>` |

##### Standard directpath
The NIC stays bound to the kernel's `mlx5_core` driver. Each runtime opens
the NIC through rdma-core and creates its own queues and steering rules.
Runtimes use flow steering (software-managed steering tables) when the NIC
supports it and fall back to queue steering (RSS) otherwise. For best
performance, NIC firmware must include support for User Context Objects
(DEVX) and Software Managed Steering Tables. For the ConnectX-5, the firmware
version must be at least 16.26.1040. Additionally, directpath requires Linux
kernel version 5.0.0 or newer. Mellanox OFED is no longer required: Caladan
builds its own rdma-core and uses the kernel's in-tree `mlx5_core` and
`mlx5_ib` drivers.

To enable directpath, add `enable_directpath 1` to the config file for all
runtimes that should use directpath (`enable_directpath fs` or
`enable_directpath qs` forces flow steering or queue steering), and inform the
IOKernel of the NIC's PCI address by starting it with the extra arguments
`nicpci <pci address>`. Each runtime launched with directpath must currently
run as root and have a unique IP address.

##### VFIO directpath
The IOKernel owns the whole NIC and manages it from user space through
rdma-core's mlx5 VFIO provider, which issues firmware commands directly. It
creates each runtime's queues, RSS table and steering rules, and passes the
runtime its queue memory and a doorbell page. It also wakes runtimes on NIC
completion events and forwards ARP requests. All runtimes acquire directpath
queues when the IOKernel is in VFIO mode and do not need to be started with
root.

NIC firmware must report the `umem_uid_0` capability, which rdma-core's VFIO
provider checks when it opens the device, and must support receive queues
backed by a shared receive pool (RMP). Support for both features was added to
firmware in early 2022. For the ConnectX-5, this was in the 16.32.x firmware
release. You can check the version before binding the NIC to `vfio-pci` with `ethtool -i <ifname>`
or `ibv_devinfo`.

VFIO directpath also requires an enabled IOMMU (for Intel CPUs, add
`intel_iommu=on` to the kernel boot parameters). Bring down the NIC's Linux
interface, bind the NIC to `vfio-pci`, and start the IOKernel with `vfio`:
```
sudo ip link set down <ifname>
sudo modprobe vfio-pci
sudo ./dpdk/usertools/dpdk-devbind.py -b vfio-pci <pci address>
sudo ./iokerneld vfio nicpci <pci address>
```

### Storage
This code has been tested with an Intel Optane SSD 900P Series NVMe device.
If your device has op latencies that are greater than 10us, consider updating the device_latency_us
variable (or the known_devices list) in runtime/storage.c.

## More Examples

#### Running a simple block storage server
Ensure that you have compiled Caladan with storage support by setting the appropriate flag in build/config,
and that you have built the loadgen client application.

Compile the C++ bindings and the storage server:
```
make -C bindings/cc
make -C apps/storage_service
```

On the server:
```
sudo ./iokerneld
sudo spdk/scripts/setup.sh
sudo apps/storage_service/storage_server storage_server.config
```

On the client:
```
sudo ./iokerneld
sudo apps/loadgen/target/release/loadgen --config=storage_client.config --mode=runtime-client --mpps=0.55 --protocol=reflex --runtime=10 --samples=10 --threads=20 --transport=tcp 192.168.1.3:5000
```

#### Running with interference

Ensure that you have built the loadgen application on client and server.

Compile the C++ bindings and the memory/cache antagonist:
```
make -C bindings/cc
make -C apps/netbench
```

On the server, run the IOKernel with the interference-aware scheduler (ias),
the loadgen application, and the cache antagonist:
```
sudo ./iokerneld ias
./apps/loadgen/target/release/loadgen 192.168.1.8:5000 --config victim.config --mode spawner-server
./apps/netbench/stress antagonist.config 20 10 cacheantagonist:4090880
```

On the client:
```
sudo ./iokerneld
./apps/loadgen/target/release/loadgen 192.168.1.8:5000 --config client.config --mode runtime-client
```

You should observe that you can stop and start the antagonist and that the
loadgen application's latency is not impacted. In contrast, if you use
Shenango's default scheduler (`sudo ./iokerneld`) on the server, when you run
the antagonist with the loadgen application, the loadgen application's
latency degrades.
