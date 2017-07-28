#!/home/sheffler/venv/david/bin/ipython
from sys import argv
from pyrosetta import *
from pdb_utils_noclass import *
from pyrosetta.toolbox import pose_from_rcsb
from repeat_utils import *
import random,string
from math import *
from xyzMath import *
#from two_sided_design_pyr import *
import pickle
from rif.geom.ray_hash import RayRay10dHash
from rif.geom import Ray
from rosetta.numeric import xyzVector_double_t as V3
from rosetta.numeric import xyzMatrix_double_t as M3
from hash_subclass import *

def choose_torsions(frange,aa_type):
    MAX_TRIES=20
    ntries=0
    found=0
    for i in range(MAX_TRIES):
      ntries=ntries+1
      phi =-75. + ran_range(frange)
      psi =145. +  ran_range(frange)
      if eval_rama(aa_type,phi,psi) < 1.5:
        found=1
        break

    if found==0: print 'no torsions found'
    return phi,psi  # if not found, then return last phi psi pair sampled

def generate_peptides(repeat_L,Nsamples,frange,dump_pdb):
  p=Pose()
  pdbs={}
  N_repeats=14%repeat_length
  length=N_repeats*repeat_L
  seq=""
  for i in range(length):seq=seq+"A"
  rosetta.core.pose.make_pose_from_sequence(p, seq,"fa_standard")
  torsions=[]
  helical_params=[]
  phiL=[]
  psiL=[]
  for i in range(Nsamples):
    for j in range(repeat_L):
        phi,psi=  choose_torsions(frange,'THR')
        phiL.append(phi)
        phiL.append(psi)
        
        torsions.append( (phi,psi) )
    
    for start in [1+repeat_L*n for n in range(N_repeats)]:
      
      for k in range(repeat_L):  
        p.set_phi(start+k,phi[k])
        p.set_psi(start+k,psi[k])
        p.set_omega(j,180.)

    if dump_pdb:    p.dump_pdb('test_%s.pdb'%i)

    res1=[Vec(p.residue(1).xyz("N")),Vec(p.residue(1).xyz("CA")),Vec(p.residue(1).xyz("C"))]
    res2=[Vec(p.residue(3).xyz("N")),Vec(p.residue(3).xyz("CA")),Vec(p.residue(3).xyz("C"))]
    trans, radius, ang =  get_helix_params(res1,res2)
    helical_params.append( (trans,radius,ang) )
    p=center_on_z_axis(res1,res2,p)
    pdbs[i]=p.clone()
    if dump_pdb:   p.dump_pdb('test_%s_tf.pdb'%i)
    yield [phi1,psi1,phi2,psi2], p.clone(), (trans,radius,ang)
  # return torsions, pdbs, helical_params

def dock_peptide(p,nbins): 
# have match between repeat protein q and peptide p. now sample helical degrees of freedom to dock p on q
        for dis in range(nbins):
         for angle in range(nbins*6):
          deg=360.*float(angle)/float(nbins*6.)
          dist=-3.+6*(float(dis)/float(nbins))
#don't want p to be moved. the following is a bit silly          
          
          b=rotate_around_z( Vec(0.,0.,1.0),deg,p.clone())
          c=translate_along_z(dist,b.clone())
#          c.append_pose_by_jump(q.clone(),1)
#          c.dump_pdb('%s_%s_combo_%s_%s_tf.pdb'%(DHR[0:base],p_index,angle,dist))
          yield(c, deg,dist)
  
def compare_params(pept_gen, DHR,names):
    trans_threshold=2.0  # difference in translation/repeat (Angstroms)
    rot_threshold=0.6  # difference in rotation/repeat (radians)
    matches={}
    Nmatch=0
    for d in names:
        matches[d]=[]
    #for j in range(len(pept)):
    for torsions, pdb, p in pept_gen:
        for i in range(len(DHR)):
            d=DHR[i]
            for n in range(1,3): # check for 1 or 2 peptide repeats equivalent to 1 repeat protein repeat
             if ( abs(d[0] -n*p[0]) < trans_threshold and abs(d[2]-n*p[2]) < rot_threshold) :
                #print('match  %s %s'%(names[i],j))
                matches[names[i]].append( (pdb.clone(),p,torsions) )
                Nmatch=Nmatch+1
    return Nmatch,matches

############################################################
init_pyrosetta()
input_file=argv[1] # list of repeat proteins
nbins=int(argv[2]) # resolution of docking grid sampling
npept=int(argv[3])
#Nstruct, angle variance, output_pdb
# use generator to avoid memory cost of storing all structures
print 'set up  peptide backbone generator '
pept_gen = generate_peptides(3,npept,20.,0)  #repeat_length, Nstruct, angle variance, output_pdb

print 'get repeat protein params '
DHR_params, DHR_arcs, names, lengths, rep_structs = calc_repeat_protein_params_ws(input_file)

print 'generate peptides and compare helical params to those of repeat proteins'
Nmatch, matches=compare_params(pept_gen,DHR_params,names)
print('Number of matches: %s '%Nmatch)

hash_nc=use_hash_rot(1.0,3.0,"bb_asn_dict_combo_1.0_rot0")
for DHR in matches.keys():
    print DHR_arcs[DHR],len(matches[DHR])
    q=rep_structs[DHR]
    pept_match=[]
    for i in range(len(matches[DHR])):
        print 'docking peptide %s'%i
        p=matches[DHR][i][0]
        pept_params=matches[DHR][i][1]
        torsions=matches[DHR][i][2]
        arc_length=sqrt( pept_params[0]**2 + (pept_params[1] * sin(pept_params[2] )**2  ) )
        print('%s %.2f %.2f %.2f  %.2f'%(i,pept_params[0],pept_params[1],pept_params[2],arc_length))
        base=DHR.index('.')

        continue
        dock_gen=dock_peptide(p,nbins)
        print 'evaluate number of contacts and clashes for each dock of peptide'
        good_matches,contact_hist, ntries=eval_contacts_pair(q,dock_gen,20)  #need to fix now that have generator

# now screen matches to count number of asn-bb hbonds
    
        print 'contacts: ', ntries, len(good_matches),contact_hist
        for match in good_matches:
         pdb=match[0].clone()
         n_sc_bb=hash_nc.count_asn_bb(pdb,q)
         print('number asn-bb hbonds %s'%n_sc_bb)
         if n_sc_bb > 0:
            new_pdb=pdb.clone() 
	    new_pdb.append_pose_by_jump(q.clone(),1)
 #           params=match[1]
#            p_index=params[0]
            trans=round(pept_params[0],1)
            twist=round(pept_params[2],1)
            angle=round(match[1],2)
            dist=round(match[2],2)
#        print('%s %s %4.1f %4.1f %4.1f %4.1f %4.1f %4.1f'%(DHR,nangle,dist,torsions[0],torsions[1],torsions[2],torsions[3])) 
            new_pdb.dump_pdb('%s_%s_%4.1f_%4.1f_%4.1f_%4.1f_%s_%s.pdb'%(DHR[0:base],n_sc_bb,torsions[0],torsions[1],torsions[2],torsions[3],angle,dist))
            print('%s_%s_%4.1f_%4.1f_%4.1f_%4.1f_%s_%s.pdb'%(DHR[0:base],n_sc_bb,torsions[0],torsions[1],torsions[2],torsions[3],angle,dist))
            print('%s %s %s %4.1f %4.1f %4.1f %4.1f %s %s %s %s'%(DHR[0:base],angle,dist,torsions[0],torsions[1],torsions[2],torsions[3],match[2],n_sc_bb,trans,twist))