"use client";

import { useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Torus } from "@react-three/drei";
import * as THREE from "three";

function PulsingTorus({ speed = 0.4 }: { speed?: number }) {
  const outerRef = useRef<THREE.Mesh>(null);
  const innerRef = useRef<THREE.Mesh>(null);
  const glowRef  = useRef<THREE.Mesh>(null);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();

    if (outerRef.current) {
      outerRef.current.rotation.x = t * speed * 0.6;
      outerRef.current.rotation.y = t * speed;
    }
    if (innerRef.current) {
      innerRef.current.rotation.x = -t * speed * 0.9;
      innerRef.current.rotation.z = t * speed * 0.4;
    }
    if (glowRef.current) {
      const s = 1 + Math.sin(t * 2) * 0.04;
      glowRef.current.scale.setScalar(s);
    }
  });

  return (
    <group>
      {/* Outer ring */}
      <Torus
        ref={outerRef}
        args={[1.4, 0.04, 16, 120]}
      >
        <meshStandardMaterial
          color="#F59E0B"
          emissive="#F59E0B"
          emissiveIntensity={1.2}
          roughness={0.1}
          metalness={0.8}
        />
      </Torus>

      {/* Inner ring — tilted */}
      <Torus
        ref={innerRef}
        args={[0.9, 0.03, 16, 120]}
        rotation={[Math.PI / 4, 0, 0]}
      >
        <meshStandardMaterial
          color="#E5E7EB"
          emissive="#E5E7EB"
          emissiveIntensity={0.5}
          roughness={0.2}
          metalness={0.9}
        />
      </Torus>

      {/* Glow sphere */}
      <mesh ref={glowRef}>
        <sphereGeometry args={[0.18, 16, 16]} />
        <meshStandardMaterial
          color="#F59E0B"
          emissive="#F59E0B"
          emissiveIntensity={3}
          transparent
          opacity={0.7}
        />
      </mesh>

      {/* Ambient point lights */}
      <pointLight position={[2, 2, 2]}   color="#F59E0B" intensity={2} />
      <pointLight position={[-2, -1, -2]} color="#E11D48" intensity={0.6} />
      <ambientLight intensity={0.1} />
    </group>
  );
}

export default function Visualizer3D() {
  return (
    <div className="w-full h-full min-h-[320px]">
      <Canvas
        camera={{ position: [0, 0, 4], fov: 45 }}
        gl={{ antialias: true, alpha: true }}
        style={{ background: "transparent" }}
      >
        <PulsingTorus />
        <OrbitControls
          enablePan={false}
          enableZoom={false}
          autoRotate
          autoRotateSpeed={0.8}
        />
      </Canvas>
    </div>
  );
}
