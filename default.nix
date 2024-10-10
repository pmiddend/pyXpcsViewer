let
  pkgs = import <nixpkgs> { };
in
pkgs.mkShell {
  buildInputs = [
    # mainPackage
    (pkgs.python3.withPackages (ps: with ps; [
      pyqt5
      h5py
      hdf5plugin
      matplotlib
      pyqtgraph
      scikit-learn
      tqdm
    ]))
    pkgs.qt5.wrapQtAppsHook
    pkgs.makeWrapper
    pkgs.bashInteractive
  ];

  shellHook = ''
    bashdir=$(mktemp -d)
    makeWrapper "$(type -p bash)" "$bashdir/bash" "''${qtWrapperArgs[@]}"
    exec "$bashdir/bash"
  '';
}
